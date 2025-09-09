"""
API Models

Pydantic models for API requests and responses:
- IngestionTriggerRequest/Response: For triggering ingestion
- StatusResponse: For monitoring endpoint
- ErrorResponse: For error handling
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IngestionTriggerRequest(BaseModel):
    """Request model for triggering data ingestion."""

    file_path: Optional[str] = Field(None, description="Path to data file (optional, uses config default)")


class IngestionTriggerResponse(BaseModel):
    """Response model for ingestion trigger."""

    batch_id: str = Field(..., description="Unique batch identifier")
    status: str = Field(..., description="Ingestion status")
    message: str = Field(..., description="Status message")
    stats: Dict[str, Any] = Field(..., description="Ingestion statistics")


class SubmissionTriggerResponse(BaseModel):
    """Response model for submission trigger."""

    batch_id: str = Field(..., description="Unique batch identifier")
    status: str = Field(..., description="Submission status")
    message: str = Field(..., description="Status message")
    stats: Dict[str, Any] = Field(..., description="Submission statistics")


class StatusResponse(BaseModel):
    """Response model for status/monitoring endpoint."""

    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    environment: str = Field(..., description="Deployment environment")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")

    # Ingestion metrics
    total_records: int = Field(..., description="Total records in database")
    processed_records: int = Field(..., description="Records processed but not submitted")
    submitted_records: int = Field(..., description="Records successfully submitted to OpenMRS")
    failed_records: int = Field(..., description="Records that failed submission")
    dlq_records: int = Field(..., description="Records in dead letter queue")

    # Performance metrics
    average_ingestion_time_ms: Optional[float] = Field(None, description="Average ingestion processing time")
    average_submission_time_ms: Optional[float] = Field(None, description="Average submission processing time")

    # Recent activity
    last_ingestion_batch: Optional[str] = Field(None, description="Last ingestion batch ID")
    last_submission_batch: Optional[str] = Field(None, description="Last submission batch ID")
    last_activity: Optional[datetime] = Field(None, description="Timestamp of last activity")


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error: str = Field(..., description="Error type or code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    request_id: Optional[str] = Field(None, description="Request ID for tracing")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str = Field(..., description="Health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    version: Optional[str] = Field(None, description="Service version")
