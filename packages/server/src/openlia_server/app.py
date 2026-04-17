"""FastAPI application factory."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Build the FastAPI app. Phase 1+ will register routers here."""
    app = FastAPI(title="OpenLIA", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
