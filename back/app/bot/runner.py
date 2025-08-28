from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import logging

from sqlmodel import Session, select

from ..db import engine
from ..models import ChatMessage, AiSettings, Task, Project
logger = logging.getLogger("bot")


def _setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logger.info("Logging initialized with level=%s", level)


def _mask_secret(value: Optional[str]) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 6:
        return "*" * len(value)
    return value[:3] + "*" * (len(value) - 6) + value[-3:]

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore


def _reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Очистить контекст")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def _build_tasks_context(session: Session, owner_id: Optional[int]) -> str:
    statement = select(Task, Project).join(Project, isouter=True)
    if owner_id is not None:
        statement = statement.where((Task.owner_id == owner_id) | (Task.owner_id.is_(None)))
    rows = session.exec(statement).all()
    lines: List[str] = []
    for task, project in rows:
        lines.append(
            "\n".join([
                f"ID: {task.id}",
                f"Заголовок: {task.title}",
                f"Описание: {task.description or ''}",
                f"Дедлайн: {task.deadline.isoformat() if task.deadline else '-'}",
                f"Длительность(ч): {task.duration_hours}",
                f"Приоритет: {task.priority}",
                f"Важность: {task.importance}",
                f"Тип: {task.kind}",
                f"Начало события: {task.event_start.isoformat() if task.event_start else '-'}",
                f"Окончание события: {task.event_end.isoformat() if task.event_end else '-'}",
                f"Проект: {project.name if project else '-'}",
            ])
        )
        lines.append("-")
    if not lines:
        return "Открытых задач нет."
    return "\n".join(["Текущие открытые задачи:"] + lines)


def _get_ai_settings(session: Session, owner_id: Optional[int]) -> AiSettings:
    logger.debug("Fetching AiSettings for owner_id=%s", owner_id)
    owner_settings = None
    if owner_id is not None:
        owner_settings = session.exec(select(AiSettings).where(AiSettings.owner_id == owner_id)).first()
        logger.debug("Owner-specific AiSettings found=%s", bool(owner_settings))
    global_settings = session.exec(select(AiSettings).where(AiSettings.owner_id == 0)).first()
    logger.debug("Global AiSettings found=%s", bool(global_settings))

    # Prefer owner settings if it has a non-empty key; otherwise fallback to global with key
    def has_key(s: Optional[AiSettings]) -> bool:
        return bool(s and s.openai_api_key and len(s.openai_api_key) > 0)

    chosen = owner_settings if has_key(owner_settings) else (global_settings if has_key(global_settings) else (owner_settings or global_settings))
    if not chosen:
        chosen = AiSettings(owner_id=owner_id or 0)
        session.add(chosen)
        session.commit()
        session.refresh(chosen)
        logger.debug("Created new AiSettings row for owner_id=%s", chosen.owner_id)

    logger.info("AiSettings resolved: owner_id=%s, has_key=%s, model=%s",
                chosen.owner_id,
                bool(chosen.openai_api_key and len(chosen.openai_api_key) > 0),
                chosen.openai_model)
    return chosen


def _estimate_context_usage_chars(messages: List[Dict[str, str]], max_chars: int) -> float:
    total = 0
    for m in messages:
        total += len(m.get("role", "")) + len(m.get("content", ""))
    return total / max_chars if max_chars > 0 else 0.0


async def main() -> None:
    _setup_logging()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    logger.info("Starting bot. TELEGRAM_BOT_TOKEN present=%s", bool(token))
    logger.info("DATABASE_URL=%s", os.getenv("DATABASE_URL"))

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def on_start(message: Message) -> None:
        await message.answer(
            "Привет! Я помогу с задачами.\n"
            "— Введите ваш запрос, я отвечу на основе текущих открытых задач.\n"
            "— Нажмите кнопку \"Очистить контекст\" чтобы начать заново.",
            reply_markup=_reply_kb(),
        )

    @dp.message(F.text.casefold() == "очистить контекст")
    @dp.message(F.text.casefold() == "/clear")
    async def on_clear(message: Message) -> None:
        owner_id = message.from_user.id if message.from_user else 0
        with Session(engine) as session:
            msgs = session.exec(select(ChatMessage).where(ChatMessage.owner_id == (owner_id or 0))).all()
            for m in msgs:
                session.delete(m)
            session.commit()
        await message.answer("Контекст очищен.", reply_markup=_reply_kb())

    @dp.message(F.text)
    async def on_text(message: Message) -> None:
        text = message.text or ""
        owner_id = message.from_user.id if message.from_user else 0
        chat_id = message.chat.id
        logger.info("Incoming message: from=%s chat=%s len=%s", owner_id, chat_id, len(text))

        with Session(engine) as session:
            # Persist user message
            if text:
                session.add(ChatMessage(owner_id=owner_id, role="user", content=text, created_at=datetime.utcnow()))
                session.commit()

            ai = _get_ai_settings(session, owner_id)
            if not ai.openai_api_key:
                logger.warning("No OpenAI API key for owner_id=%s; replying with hint", owner_id)
                await message.answer("Не задан API токен ChatGPT. Задайте его в настройках приложения.", reply_markup=_reply_kb())
                return
            if OpenAI is None:
                await message.answer("OpenAI клиент не установлен на сервере.", reply_markup=_reply_kb())
                return

            system_context = _build_tasks_context(session, owner_id)
            history = session.exec(select(ChatMessage).where(ChatMessage.owner_id == owner_id).order_by(ChatMessage.created_at.asc())).all()
            messages: List[Dict[str, str]] = [{"role": "system", "content": f"Ты помощник по управлению задачами. Вот контекст.\n\n{system_context}"}]
            for h in history[-30:]:
                messages.append({"role": h.role, "content": h.content})
            logger.debug("Prepared messages: count=%s (including system)", len(messages))

        MAX_CHARS = 100000
        usage = _estimate_context_usage_chars(messages, MAX_CHARS)
        if usage >= 0.85:
            await message.answer("Внимание: контекст диалога достиг 85% от лимита. Рекомендуется очистить контекст.", reply_markup=_reply_kb())

        try:
            client = OpenAI(api_key=ai.openai_api_key)
            completion = client.chat.completions.create(
                model=ai.openai_model or "gpt-4o",
                messages=messages,
                temperature=0.2,
            )
            answer = completion.choices[0].message.content or ""
            logger.info("OpenAI call ok: model=%s answer_len=%s", ai.openai_model, len(answer))
        except Exception as e:
            logger.exception("OpenAI call failed: %s", e)
            await message.answer(f"Ошибка при обращении к ChatGPT API: {e}", reply_markup=_reply_kb())
            return

        # store assistant reply
        with Session(engine) as session:
            session.add(ChatMessage(owner_id=owner_id, role="assistant", content=answer, created_at=datetime.utcnow()))
            session.commit()

        await message.answer(answer, reply_markup=_reply_kb())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


