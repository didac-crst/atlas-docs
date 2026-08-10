from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from atlasdocs import __version__
from atlasdocs.api.routes import router as api_router
from atlasdocs.config import get_settings
from atlasdocs.ui.routes import SPA_DIR, router as ui_router


def create_app() -> FastAPI:
    # Validate production session settings at startup.
    get_settings()
    app = FastAPI(title="AtlasDocs", version=__version__)
    app.include_router(api_router)
    app.include_router(ui_router)

    assets_dir = SPA_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/ui/assets", StaticFiles(directory=str(assets_dir)), name="ui-assets")

    # Keep legacy /static mount only if present (logo copies, etc.).
    static_dir = Path(__file__).resolve().parent.parent / "ui" / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    def root() -> RedirectResponse:
        """Send bare host roots into the SPA shell; auth routing stays under /ui."""
        return RedirectResponse(url="/ui", status_code=307)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
