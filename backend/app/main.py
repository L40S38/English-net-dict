from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.migrations import run_alembic_migrations
from app.config import settings
from app.routers import chat, etymology_components, groups, images, phrases, words


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(words.router)
    app.include_router(etymology_components.router)
    app.include_router(images.router)
    app.include_router(chat.router)
    app.include_router(groups.router)
    app.include_router(phrases.router)

    static_dir = Path(settings.data_dir)
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.on_event("startup")
    def startup() -> None:
        run_alembic_migrations()

    return app


app = create_app()
