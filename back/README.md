FastAPI backend for Telegram WebApp
===================================

Endpoints
---------
- GET `/health`: Health check
- POST `/auth/telegram`: Exchange Telegram WebApp `initData` for a JWT
- GET `/users/me`: Return the user payload (Bearer token required)

Environment
-----------
Create `.env` at the repo root (next to `docker-compose.yml`) based on `.env.example`:

```
JWT_SECRET=your-strong-secret
TELEGRAM_BOT_TOKEN=123456:your-bot-token
```

Run
---

Docker Compose:

```
docker compose up --build
```

Auth flow (Telegram WebApp)
---------------------------
From the WebApp, send `Telegram.WebApp.initData` as-is to `POST /auth/telegram` in JSON body `{ "init_data": "..." }`. The backend verifies the signature using your bot token and returns a JWT you can use as `Authorization: Bearer <token>` for protected endpoints.

