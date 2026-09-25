from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, dashboard, documents, health, qa, quiz
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.models.database import init_db

settings = get_settings()
configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("%s started in '%s' mode.", settings.APP_NAME, settings.ENV)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="An adaptive, RAG-grounded AI tutor built on the student's own course materials.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: permissive for local development; tighten to explicit origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENV != "production" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "An internal error occurred."})


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(qa.router)
app.include_router(quiz.router)
app.include_router(dashboard.router)

# Serve the static frontend (single-page vanilla app) if present.
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
