"""
Monitoring API

FastAPI router for monitoring endpoints:
- GET /status: Returns ingestion and submission metrics and service health
"""
from __future__ import annotations

import logging
import time
from datetime import datetime

from fastapi import APIRouter, Request

from ..core.config import get_settings
from ..models.api_models import StatusResponse

router = APIRouter()
logger = logging.getLogger(__name__)

_start_time = time.time()


@router.get("/status", response_model=StatusResponse)
async def status_endpoint(request: Request) -> StatusResponse:
    """Return service status and ingestion metrics."""
    settings = get_settings()
    mongo_service = request.app.state.mongo_service

    stats = await mongo_service.get_ingestion_stats()

    uptime_seconds = time.time() - _start_time

    response = StatusResponse(
        service=settings.APP_NAME,
        version="1.0.0",
        environment=settings.ENV,
        uptime_seconds=uptime_seconds,
        total_records=stats.get("total_records", 0),
        processed_records=stats.get("processed_records", 0),
        submitted_records=stats.get("submitted_records", 0),
        failed_records=stats.get("failed_records", 0),
        dlq_records=stats.get("dlq_records", 0),
        average_ingestion_time_ms=None,
        average_submission_time_ms=None,
        last_ingestion_batch=None,
        last_submission_batch=None,
        last_activity=datetime.utcnow(),
    )

    logger.info("status_requested", environment=settings.ENV)
    return response
