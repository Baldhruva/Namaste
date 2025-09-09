"""
Ingestion API

FastAPI router for data ingestion endpoints:
- POST /ingest/trigger: Manually trigger ingestion process
- POST /submit/trigger: Manually trigger submission process
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from ..core.logging import bind_context
from ..models.api_models import IngestionTriggerRequest, IngestionTriggerResponse, SubmissionTriggerResponse
from ..services.ingestion_service import IngestionService

router = APIRouter()
logger = logging.getLogger(__name__)


def get_ingestion_service(request: Request) -> IngestionService:
    """Dependency to get ingestion service from app state."""
    return request.app.state.ingestion_service


@router.post("/trigger", response_model=IngestionTriggerResponse)
async def trigger_ingestion(
    request: IngestionTriggerRequest,
    background_tasks: BackgroundTasks,
    req: Request,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> IngestionTriggerResponse:
    """Trigger TM2 data ingestion from file.

    This endpoint starts a background task to process TM2 dataset files,
    validate records, transform data, and store in MongoDB.
    """
    request_id = req.state.request_id

    with bind_context(logger, request_id=request_id):
        logger.info("ingestion_triggered", file_path=request.file_path)

        try:
            # Validate file path if provided
            file_path = None
            if request.file_path:
                file_path = Path(request.file_path)
                if not file_path.exists():
                    raise HTTPException(status_code=400, detail=f"File not found: {request.file_path}")
                if not file_path.is_file():
                    raise HTTPException(status_code=400, detail=f"Path is not a file: {request.file_path}")

            # Start background ingestion
            background_tasks.add_task(run_ingestion_background, ingestion_service, file_path, request_id)

            return IngestionTriggerResponse(
                batch_id="",  # Will be set by background task
                status="started",
                message="Ingestion started in background",
                stats={},
            )

        except Exception as e:
            logger.error("ingestion_trigger_error", error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to start ingestion: {str(e)}")


@router.post("/submit/trigger", response_model=SubmissionTriggerResponse)
async def trigger_submission(
    background_tasks: BackgroundTasks,
    req: Request,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> SubmissionTriggerResponse:
    """Trigger submission of pending records to OpenMRS.

    This endpoint starts a background task to submit processed TM2 records
    to the OpenMRS REST API.
    """
    request_id = req.state.request_id

    with bind_context(logger, request_id=request_id):
        logger.info("submission_triggered")

        try:
            # Start background submission
            background_tasks.add_task(run_submission_background, ingestion_service, request_id)

            return SubmissionTriggerResponse(
                batch_id="",  # Will be set by background task
                status="started",
                message="Submission started in background",
                stats={},
            )

        except Exception as e:
            logger.error("submission_trigger_error", error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to start submission: {str(e)}")


async def run_ingestion_background(
    ingestion_service: IngestionService,
    file_path: Path | None,
    request_id: str,
) -> None:
    """Background task to run data ingestion."""
    with bind_context(logger, request_id=request_id):
        try:
            stats = await ingestion_service.ingest_from_file(file_path)
            logger.info("background_ingestion_completed", **stats)

        except Exception as e:
            logger.error("background_ingestion_error", error=str(e))
            # Could send notification or update status here


async def run_submission_background(
    ingestion_service: IngestionService,
    request_id: str,
) -> None:
    """Background task to run record submission."""
    with bind_context(logger, request_id=request_id):
        try:
            stats = await ingestion_service.submit_pending_records()
            logger.info("background_submission_completed", **stats)

        except Exception as e:
            logger.error("background_submission_error", error=str(e))
            # Could send notification or update status here
