"""FastAPI 入口。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import companies, graph, industries, relations, settings as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时确保 SQLite 配置库就绪
    from . import settings_db

    settings_db.get_engine()
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(settings_router.router)
app.include_router(companies.router)
app.include_router(industries.router)
app.include_router(relations.router)
app.include_router(graph.router)


@app.get("/")
async def root() -> dict:
    return {"name": settings.app_name, "version": settings.app_version}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}