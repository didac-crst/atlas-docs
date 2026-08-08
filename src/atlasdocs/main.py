"""ASGI entrypoint: uvicorn atlasdocs.main:app"""

from atlasdocs.api import app

__all__ = ["app"]
