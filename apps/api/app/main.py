from fastapi import FastAPI

from .api.routes_documents import router as documents_router
from .api.routes_query import router as query_router
from .core.logging import configure_logging
from .db.init_db import init_db
from .services.opensearch_index import ensure_index


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="DocSearch API", version="0.1.0")

    app.include_router(documents_router, prefix="/documents", tags=["documents"])
    app.include_router(query_router, prefix="/query", tags=["query"])

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {"status": "ok"}

    @app.on_event("startup")
    async def _startup() -> None:
        await init_db()
        # Ensure OpenSearch index exists for keyword retrieval.
        ensure_index()

    return app


app = create_app()
