import asyncio
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.migrations import run_alembic_migrations
from server.routers import (
    audio,
    chat,
    etymology_components,
    groups,
    images,
    listening,
    migration,
    phrases,
    search,
    words,
)


def _install_windows_proactor_connection_reset_filter() -> None:
    """Suppress benign ConnectionResetError noise on Windows ProactorEventLoop.

    When a keep-alive HTTP client disconnects, uvicorn calls socket.shutdown()
    which raises WinError 10054 from inside `_ProactorBasePipeTransport._call_connection_lost`.
    The exception is harmless (the connection is already gone) but pollutes stderr.
    """

    if sys.platform != "win32":
        return
    loop = asyncio.get_event_loop()
    original_handler = loop.get_exception_handler()

    def handler(inner_loop: asyncio.AbstractEventLoop, context: dict) -> None:
        exc = context.get("exception")
        exc_type = type(exc).__name__ if exc else ""
        exc_msg = str(exc) if exc else ""
        is_conn_reset = "10054" in exc_msg or "ConnectionReset" in exc_type
        if is_conn_reset and "_call_connection_lost" in context.get("message", ""):
            return
        if original_handler is not None:
            original_handler(inner_loop, context)
        else:
            inner_loop.default_exception_handler(context)

    loop.set_exception_handler(handler)


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
    app.include_router(audio.router)
    app.include_router(chat.router)
    app.include_router(listening.router)
    app.include_router(groups.router)
    app.include_router(phrases.router)
    app.include_router(search.router)
    app.include_router(migration.router)

    static_dir = Path(settings.data_dir)
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.exists():
        assets_dir = frontend_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str) -> FileResponse:
            candidate = (frontend_dist / full_path).resolve()
            try:
                candidate.relative_to(frontend_dist.resolve())
            except ValueError:
                return FileResponse(frontend_dist / "index.html")
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(frontend_dist / "index.html")

    @app.on_event("startup")
    def startup() -> None:
        run_alembic_migrations()
        _install_windows_proactor_connection_reset_filter()

    return app


app = create_app()
