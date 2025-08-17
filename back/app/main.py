from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .routers import health as health_router
from .routers import auth as auth_router
from .routers import users as users_router
from .routers import projects as projects_router
from .routers import tasks as tasks_router
from .routers import settings as settings_router
from .routers import stats as stats_router
from .routers import events as events_router
from .db import init_db


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router.router)
    app.include_router(auth_router.router)
    app.include_router(users_router.router)
    app.include_router(projects_router.router)
    app.include_router(tasks_router.router)
    app.include_router(settings_router.router)
    app.include_router(stats_router.router)
    app.include_router(events_router.router)

    @app.get("/")
    def root():
        return {"name": settings.app_name}

    return app


init_db()
app = create_app()

