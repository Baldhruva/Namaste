"""
TM2 Ingestion Service Package

This package contains the core components of the TM2 data ingestion service:
- core: Configuration, logging, and MongoDB infrastructure
- services: Business logic for MongoDB, OpenMRS, and ingestion
- models: Pydantic data models for TM2 data and API schemas
- api: FastAPI routers for ingestion and monitoring endpoints
"""

__version__ = "1.0.0"
__all__ = ["core", "services", "models", "api"]
