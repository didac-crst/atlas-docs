from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from atlasdocs import __version__
from atlasdocs.api.routes import router as api_router
from atlasdocs.config import get_settings
from atlasdocs.ui.routes import router as ui_router


def create_app() -> FastAPI:
    # Validate production session settings at startup.
    get_settings()
    app = FastAPI(title="AtlasDocs", version=__version__)
    static_dir = Path(__file__).resolve().parent.parent / "ui" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.include_router(api_router)
    app.include_router(ui_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
