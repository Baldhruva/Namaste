"""
API Package

Contains FastAPI routers for:
- ingestion_api: /ingest/trigger endpoint and background ingestion task
- monitoring_api: /status endpoint for ingestion metrics
"""

__all__ = ["ingestion_api", "monitoring_api"]
