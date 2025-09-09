"""
TM2 Ingestion Service - FastAPI Application Entrypoint

This is the main entrypoint for the TM2 data ingestion service. It sets up:
- FastAPI application with CORS middleware
- Structured JSON logging with contextual fields
- MongoDB client initialization with indexes
- Service dependencies (MongoService, OpenMRSClient, IngestionService)
- API routers for ingestion and monitoring
- Request ID middleware for tracing
- Health check endpoint

The service processes TM2 dataset files, stores transformed data in MongoDB Atlas,
and submits relevant information to OpenMRS via REST API.
"""

import asyncio
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings

import sys
import os

# Add fastapi-namaste-icd11 directory to sys.path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "fastapi-namaste-icd11"))
from app.core.logging import LogContext, bind_context, configure_logging
from app.core.mongo import Mongo
from app.services.mongo_service import MongoService
from app.services.openmrs_client import OpenMRSClient
from app.services.ingestion_service import IngestionService
from app.api.ingestion_api import router as ingestion_router
from app.api.monitoring_api import router as monitoring_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown."""
    settings = get_settings()

    # Startup
    configure_logging(settings.LOG_LEVEL)
    logger = logging.getLogger(__name__)

    with bind_context(logger, service="tm2-ingestion", env=settings.ENV):
        logger.info(f"service_startup app_name={settings.APP_NAME}")

    # Initialize MongoDB
    try:
        if settings.MONGO_URI:
            Mongo.init(settings)
    except Exception as e:
        logger.error(f"MongoDB initialization failed: {e}")

    # Initialize services
    mongo_service = MongoService(settings)
    openmrs_client = OpenMRSClient(settings)
    ingestion_service = IngestionService(settings, mongo_service, openmrs_client)

    # Attach to app state
    app.state.settings = settings
    app.state.mongo_service = mongo_service
    app.state.openmrs_client = openmrs_client
    app.state.ingestion_service = ingestion_service

    logger.info("startup_complete")

    yield

    # Shutdown
    logger.info("service_shutdown")
    Mongo.close()


# Create FastAPI app
app = FastAPI(
    title="TM2 Ingestion Service",
    description="Production-grade FastAPI service for processing TM2 datasets, storing in MongoDB Atlas, and submitting to OpenMRS",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Middleware to add request ID and timing to all requests."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    logger = logging.getLogger(__name__)
    start_time = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000
        with bind_context(logger, request_id=request_id, path=request.url.path, method=request.method, duration_ms=round(duration_ms, 2)):
            logger.exception("unhandled_exception", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error", "request_id": request_id})

    duration_ms = (time.perf_counter() - start_time) * 1000
    with bind_context(logger, request_id=request_id, path=request.url.path, method=request.method, status_code=response.status_code, duration_ms=round(duration_ms, 2)):
        logger.info("request_complete")

    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id
    return response


# Include API routers
app.include_router(ingestion_router, prefix="/api/v1", tags=["ingestion"])
app.include_router(monitoring_router, prefix="/api/v1", tags=["monitoring"])


@app.get("/", tags=["root"])
async def root():
    """Root endpoint."""
    return {"message": "Welcome to TM2 Ingestion Service", "docs": "/docs"}


@app.get("/health", tags=["health"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "tm2-ingestion"}


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_dev,
        log_level=settings.LOG_LEVEL.lower(),
    )
