"""
Catalog and health routes.

Routes:
  GET /catalog → product catalog JSON
  GET /health  → service health check with DB status
"""

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.database import get_db
from app.config import settings
from app.models.schemas import HealthResponse

router = APIRouter(tags=["Catalog & Health"])

_CATALOG_PATH = Path(__file__).parent.parent / "catalog.json"


@router.get(
    "/catalog",
    summary="Get product catalog",
    description="Returns the full product and pricing catalog used by the Sales Assistant agent.",
)
async def get_catalog():
    with open(_CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns service status and database connectivity.",
)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)[:80]}"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        database=db_status,
    )
