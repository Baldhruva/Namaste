"""
Services Package

Contains business logic services:
- mongo_service: MongoDB interaction, connection pooling, TTL indexes, audit logs, DLQ
- openmrs_client: OpenMRS REST API client with retries and resilience
- ingestion_service: TM2 data ingestion pipeline: reader, validator, transformer, persistence, submission
"""
__all__ = ["mongo_service", "openmrs_client", "ingestion_service"]
