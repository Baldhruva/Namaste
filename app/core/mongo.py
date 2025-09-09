"""
MongoDB client singleton and index management.

Provides a pooled MongoClient configured from settings and helpers to get collections.
Creates indexes for idempotency (unique) and TTL on audit collection.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection

from .config import Settings

logger = logging.getLogger(__name__)


class Mongo:
    _client: Optional[MongoClient] = None

    @classmethod
    def init(cls, settings: Settings) -> None:
        if cls._client is not None:
            return
        logger.info("mongo_connect", extra={"uri": settings.MONGO_URI})
        cls._client = MongoClient(
            settings.MONGO_URI,
            appname="tm2-ingestion-service",
            minPoolSize=2,
            maxPoolSize=50,
            tls=True,
        )
        # Create indexes
        db = cls._client[settings.MONGO_DATABASE]
        primary = db["tm2_records"]
        audit = db["tm2_audit"]
        dlq = db["tm2_dlq"]

        # Idempotency unique index
        primary.create_index([("idempotency_key", ASCENDING)], name="uniq_idempotency", unique=True)
        primary.create_index([("status", ASCENDING), ("updated_at", ASCENDING)], name="status_updated_idx")

        # TTL for audit collection
        # TTL requires a datetime field; we'll use created_at defaulting to now in writes
        ttl_seconds = int(timedelta(days=90).total_seconds())
        audit.create_index("created_at", expireAfterSeconds=ttl_seconds, name="audit_ttl")

        # DLQ useful indexes
        dlq.create_index([("created_at", ASCENDING)], name="dlq_created_idx")

    @classmethod
    def client(cls) -> MongoClient:
        if cls._client is None:
            raise RuntimeError("Mongo client not initialized. Call Mongo.init(settings) on startup.")
        return cls._client

    @classmethod
    def collection(cls, settings: Settings, which: str) -> Collection:
        client = cls.client()
        db = client[settings.MONGO_DATABASE]
        if which == "primary":
            return db["tm2_records"]
        if which == "audit":
            return db["tm2_audit"]
        if which == "dlq":
            return db["tm2_dlq"]
        raise ValueError(f"Unknown collection alias: {which}")

    @classmethod
    def close(cls) -> None:
        if cls._client is not None:
            try:
                cls._client.close()
            finally:
                cls._client = None
