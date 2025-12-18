from fastapi import FastAPI

from .api.routes_documents import router as documents_router
from .api.routes_query import router as query_router


def create_app() -> FastAPI:
    app = FastAPI(title="DocSearch API", version="0.1.0")

    app.include_router(documents_router, prefix="/documents", tags=["documents"])
    app.include_router(query_router, prefix="/query", tags=["query"])

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

