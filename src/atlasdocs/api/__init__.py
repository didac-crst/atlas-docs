from fastapi import FastAPI

from atlasdocs import __version__
from atlasdocs.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="AtlasDocs", version=__version__)
    app.include_router(router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
