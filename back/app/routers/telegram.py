from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from ..core.config import get_settings
from ..db import get_session
from ..models import ChatMessage, AiSettings, Task, Project
import logging

logger = logging.getLogger("tg-webhook")

try:
    # openai>=1.0 client
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional at runtime
    OpenAI = None  # type: ignore


router = APIRouter(prefix="/telegram", tags=["telegram"])


def _reply_keyboard() -> Dict[str, Any]:
    # Regular keyboard (not inline)
    return {
        "keyboard": [[{"text": "Очистить контекст"}]],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }


async def _tg_send_message(chat_id: int, text: str) -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=20) as client:
        await client.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "reply_markup": _reply_keyboard(),
        })


async def _tg_set_webhook() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.public_url:
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook"
    webhook_url = settings.public_url.rstrip("/") + "/telegram/webhook"
    async with httpx.AsyncClient(timeout=20) as client:
        await client.post(url, json={"url": webhook_url})


def _build_tasks_context(session: Session, owner_id: Optional[int]) -> str:
    # Include tasks for owner or global (owner_id is null)
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
    owner_settings = None
    if owner_id is not None:
        owner_settings = session.exec(select(AiSettings).where(AiSettings.owner_id == owner_id)).first()
    global_settings = session.exec(select(AiSettings).where(AiSettings.owner_id == 0)).first()

    def has_key(s: Optional[AiSettings]) -> bool:
        return bool(s and s.openai_api_key and len(s.openai_api_key) > 0)

    chosen = owner_settings if has_key(owner_settings) else (global_settings if has_key(global_settings) else (owner_settings or global_settings))
    if not chosen:
        chosen = AiSettings(owner_id=owner_id or 0)
        session.add(chosen)
        session.commit()
        session.refresh(chosen)
    return chosen


def _estimate_context_usage_chars(messages: List[Dict[str, str]], max_chars: int) -> float:
    total = 0
    for m in messages:
        total += len(m.get("role", "")) + len(m.get("content", ""))
    return total / max_chars if max_chars > 0 else 0.0


@router.post("/webhook")
async def telegram_webhook(req: Request, session: Session = Depends(get_session)):
    body = await req.json()
    logger.info("Webhook update received: keys=%s", list(body.keys()))
    message = (body.get("message") or body.get("edited_message") or {})
    if not message:
        logger.debug("No message in update")
        return {"ok": True}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    from_user = message.get("from") or {}
    owner_id = int(from_user.get("id")) if from_user.get("id") is not None else None
    text = message.get("text") or ""
    logger.info("Incoming webhook message from=%s chat=%s len=%s", owner_id, chat_id, len(text))

    if not chat_id:
        return {"ok": True}

    # /start greeting
    if text.strip().lower().startswith("/start"):
        await _tg_send_message(chat_id, (
            "Привет! Я помогу с задачами.\n"
            "— Введите ваш запрос, я отвечу на основе текущих открытых задач.\n"
            "— Нажмите кнопку \"Очистить контекст\" чтобы начать заново."
        ))
        logger.debug("Handled /start")
        return {"ok": True}

    # Handle clear context command via regular keyboard
    if text.strip().lower() in {"очистить контекст", "/clear", "clear"}:
        # Bulk delete by querying first to avoid FULL DELETE without filter
        msgs = session.exec(select(ChatMessage).where(ChatMessage.owner_id == (owner_id or 0))).all()
        for m in msgs:
            session.delete(m)
        session.commit()
        logger.info("Cleared context for owner_id=%s, removed=%s", owner_id, len(msgs))
        await _tg_send_message(chat_id, "Контекст очищен.")
        return {"ok": True}

    # Persist user message
    if text:
        session.add(ChatMessage(owner_id=owner_id or 0, role="user", content=text, created_at=datetime.utcnow()))
        session.commit()

    # Fetch AI settings
    ai = _get_ai_settings(session, owner_id)
    logger.info("AiSettings: owner_id=%s has_key=%s model=%s", ai.owner_id, bool(ai.openai_api_key), ai.openai_model)
    if not ai.openai_api_key:
        await _tg_send_message(chat_id, "Не задан API токен ChatGPT. Задайте его в настройках приложения.")
        return {"ok": True}

    if OpenAI is None:
        await _tg_send_message(chat_id, "OpenAI клиент не установлен на сервере.")
        return {"ok": True}

    # Build context: system with tasks + recent chat history
    system_context = _build_tasks_context(session, owner_id)
    history = session.exec(select(ChatMessage).where(ChatMessage.owner_id == (owner_id or 0)).order_by(ChatMessage.created_at.asc())).all()
    messages: List[Dict[str, str]] = [{"role": "system", "content": f"Ты помощник по управлению задачами. Вот контекст.\n\n{system_context}"}]
    for h in history[-30:]:  # limit tail
        messages.append({"role": h.role, "content": h.content})

    # Check context usage and notify at 85%
    MAX_CHARS = 100000
    usage = _estimate_context_usage_chars(messages, MAX_CHARS)
    logger.debug("Context usage=%.2f", usage)
    if usage >= 0.85:
        await _tg_send_message(chat_id, "Внимание: контекст диалога достиг 85% от лимита. Рекомендуется очистить контекст.")

    # Call OpenAI
    try:
        client = OpenAI(api_key=ai.openai_api_key)
        completion = client.chat.completions.create(
            model=ai.openai_model or "gpt-4o",
            messages=messages,
            temperature=0.2,
        )
        answer = completion.choices[0].message.content or ""
    except Exception as e:  # runtime robustness
        logger.exception("OpenAI call failed: %s", e)
        await _tg_send_message(chat_id, f"Ошибка при обращении к ChatGPT API: {e}")
        return {"ok": True}

    # Persist assistant message
    session.add(ChatMessage(owner_id=owner_id or 0, role="assistant", content=answer, created_at=datetime.utcnow()))
    session.commit()

    await _tg_send_message(chat_id, answer)
    logger.info("Answer sent len=%s", len(answer))
    return {"ok": True}


@router.get("/set_webhook")
async def set_webhook():
    await _tg_set_webhook()
    return {"ok": True}


