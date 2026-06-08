"""
FastAPI application entry point.

Startup:
  - Creates all DB tables (idempotent)
  - Registers API routers

Run locally:
  uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db.database import create_tables
from app.api.chat import router as chat_router
from app.api.catalog import router as catalog_router

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,   # Always DEBUG so every step is visible
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Silence noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("groq").setLevel(logging.INFO)
logging.getLogger("watchfiles").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)


# ─── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    logger.info("=" * 60)
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    logger.info("Model       : %s", settings.GROQ_MODEL)
    logger.info("DB URL      : %s", settings.DATABASE_URL[:60] + "...")
    logger.info("Memory Limit: %s messages", settings.MEMORY_CONTEXT_LIMIT)
    logger.info("=" * 60)
    await create_tables()
    logger.info("Database tables ready.")
    logger.info("Docs available at: http://localhost:8000/docs")
    logger.info("=" * 60)
    yield
    logger.info("Shutting down.")


# ─── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Persistent Sales Assistant Agent — a conversational AI that remembers context "
        "across sessions, uses real tools to answer product questions, and self-evaluates "
        "every response."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── CORS ──────────────────────────────────────────────────────────────────────
# Allow all origins (localhost, 127.0.0.1, file://, Railway, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # Must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request / Response Logging Middleware ─────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    body_bytes = await request.body()

    logger.info(">>> %s %s  |  origin=%s",
                request.method, request.url.path,
                request.headers.get("origin", "direct"))

    if body_bytes:
        try:
            body_str = body_bytes.decode("utf-8")[:300]
            logger.debug("    BODY: %s", body_str)
        except Exception:
            pass

    # Re-inject body so the route handler can read it
    async def receive():
        return {"type": "http.request", "body": body_bytes}
    request._receive = receive

    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000

    logger.info("<<< %s %s  |  status=%d  |  %.1fms",
                request.method, request.url.path,
                response.status_code, elapsed)
    return response


# ─── Routers ───────────────────────────────────────────────────────────────────
app.include_router(chat_router)
app.include_router(catalog_router)


# ─── Root ──────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse({
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "endpoints": [
            "POST /chat/{user_id}",
            "GET  /chat/{user_id}/history",
            "DELETE /chat/{user_id}/memory",
            "GET  /chat/{user_id}/evals",
            "GET  /catalog",
            "GET  /health",
        ],
    })
