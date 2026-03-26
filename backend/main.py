"""DodgeAI FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .neo4j_db import close_driver
from .routers import analytics, chat, graph, nodes, path_route


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    close_driver()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DodgeAI API",
        description="O2C graph + chat (SSE). LangGraph agent to be integrated.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(graph.router, prefix="/api", tags=["graph"])
    app.include_router(analytics.router, prefix="/api", tags=["analytics"])
    app.include_router(chat.router, prefix="/api", tags=["chat"])
    app.include_router(nodes.router, prefix="/api", tags=["nodes"])
    app.include_router(path_route.router, prefix="/api", tags=["graph"])

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
