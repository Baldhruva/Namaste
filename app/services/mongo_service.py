"""
MongoDB Service

Handles MongoDB interactions including:
- Connection pooling and collection management
- CRUD operations for TM2 records
- Audit logging with TTL
- Dead Letter Queue (DLQ) for failed records
- Idempotency checks using normalized hashes
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import UpdateOne
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from ..core.config import Settings
from ..core.mongo import Mongo

logger = logging.getLogger(__name__)


class MongoService:
    """Service for MongoDB operations with connection pooling and error handling."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._primary: Optional[Collection] = None
        self._audit: Optional[Collection] = None
        self._dlq: Optional[Collection] = None

    @property
    def primary_collection(self) -> Collection:
        if self._primary is None:
            self._primary = Mongo.collection(self.settings, "primary")
        return self._primary

    @property
    def audit_collection(self) -> Collection:
        if self._audit is None:
            self._audit = Mongo.collection(self.settings, "audit")
        return self._audit

    @property
    def dlq_collection(self) -> Collection:
        if self._dlq is None:
            self._dlq = Mongo.collection(self.settings, "dlq")
        return self._dlq

    @staticmethod
    def compute_idempotency_key(record: Dict[str, Any]) -> str:
        """Compute idempotency key from normalized record data."""
        # Normalize key fields for idempotency
        key_data = {
            "patient_identifier": record.get("patient_identifier", ""),
            "encounter_datetime": record.get("encounter_datetime", ""),
            "tm2_code": record.get("tm2_code", ""),
            "value": str(record.get("value_numeric", record.get("value_text", record.get("value_coded", "")))),
        }
        normalized = "|".join(f"{k}:{v}" for k, v in sorted(key_data.items()))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    async def upsert_record(self, record: Dict[str, Any], batch_id: str) -> bool:
        """Upsert a TM2 record using idempotency key. Returns True if inserted/updated."""
        idempotency_key = self.compute_idempotency_key(record)
        record_doc = {
            "idempotency_key": idempotency_key,
            "data": record,
            "status": "processed",
            "batch_id": batch_id,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        try:
            result = self.primary_collection.update_one(
                {"idempotency_key": idempotency_key},
                {"$set": record_doc, "$setOnInsert": {"first_seen": datetime.now(timezone.utc)}},
                upsert=True,
            )
            return result.upserted_id is not None or result.modified_count > 0
        except DuplicateKeyError:
            # Record already exists, no change needed
            return False
        except PyMongoError as e:
            logger.error("mongo_upsert_error", error=str(e), idempotency_key=idempotency_key, batch_id=batch_id)
            return False

    async def bulk_upsert_records(self, records: List[Dict[str, Any]], batch_id: str) -> Dict[str, int]:
        """Bulk upsert multiple records. Returns counts of inserted/updated."""
        operations = []
        for record in records:
            idempotency_key = self.compute_idempotency_key(record)
            record_doc = {
                "idempotency_key": idempotency_key,
                "data": record,
                "status": "processed",
                "batch_id": batch_id,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            operations.append(
                UpdateOne(
                    {"idempotency_key": idempotency_key},
                    {"$set": record_doc, "$setOnInsert": {"first_seen": datetime.now(timezone.utc)}},
                    upsert=True,
                )
            )

        try:
            result = self.primary_collection.bulk_write(operations, ordered=False)
            return {
                "inserted": result.upserted_count,
                "modified": result.modified_count,
                "matched": result.matched_count,
            }
        except PyMongoError as e:
            logger.error("mongo_bulk_upsert_error", error=str(e), batch_id=batch_id, record_count=len(records))
            return {"inserted": 0, "modified": 0, "matched": 0}

    async def get_pending_records(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get records that haven't been submitted to OpenMRS yet."""
        try:
            cursor = self.primary_collection.find(
                {"status": "processed", "submitted_at": {"$exists": False}},
                {"_id": 0, "idempotency_key": 1, "data": 1, "batch_id": 1},
            ).limit(limit)
            return list(cursor)
        except PyMongoError as e:
            logger.error("mongo_get_pending_error", error=str(e))
            return []

    async def mark_submitted(self, idempotency_key: str, success: bool, error_msg: Optional[str] = None) -> None:
        """Mark a record as submitted (success or failure)."""
        update_doc = {
            "updated_at": datetime.now(timezone.utc),
        }
        if success:
            update_doc["status"] = "submitted"
            update_doc["submitted_at"] = datetime.now(timezone.utc)
        else:
            update_doc["status"] = "submission_failed"
            update_doc["submission_error"] = error_msg

        try:
            self.primary_collection.update_one(
                {"idempotency_key": idempotency_key},
                {"$set": update_doc},
            )
        except PyMongoError as e:
            logger.error("mongo_mark_submitted_error", error=str(e), idempotency_key=idempotency_key)

    async def move_to_dlq(self, record: Dict[str, Any], error_msg: str, batch_id: str) -> None:
        """Move a failed record to the Dead Letter Queue."""
        dlq_doc = {
            "original_record": record,
            "error_message": error_msg,
            "batch_id": batch_id,
            "created_at": datetime.now(timezone.utc),
        }

        try:
            self.dlq_collection.insert_one(dlq_doc)
            # Remove from primary collection
            idempotency_key = self.compute_idempotency_key(record)
            self.primary_collection.delete_one({"idempotency_key": idempotency_key})
        except PyMongoError as e:
            logger.error("mongo_dlq_error", error=str(e), batch_id=batch_id)

    async def log_audit_event(self, event_type: str, details: Dict[str, Any], batch_id: Optional[str] = None) -> None:
        """Log an audit event to the audit collection."""
        audit_doc = {
            "event_type": event_type,
            "details": details,
            "batch_id": batch_id,
            "created_at": datetime.now(timezone.utc),
        }

        try:
            self.audit_collection.insert_one(audit_doc)
        except PyMongoError as e:
            logger.error("mongo_audit_error", error=str(e), event_type=event_type)

    async def get_ingestion_stats(self) -> Dict[str, int]:
        """Get ingestion statistics for monitoring."""
        try:
            total = self.primary_collection.count_documents({})
            processed = self.primary_collection.count_documents({"status": "processed"})
            submitted = self.primary_collection.count_documents({"status": "submitted"})
            failed = self.primary_collection.count_documents({"status": "submission_failed"})
            dlq_count = self.dlq_collection.count_documents({})

            return {
                "total_records": total,
                "processed_records": processed,
                "submitted_records": submitted,
                "failed_records": failed,
                "dlq_records": dlq_count,
            }
        except PyMongoError as e:
            logger.error("mongo_stats_error", error=str(e))
            return {
                "total_records": 0,
                "processed_records": 0,
                "submitted_records": 0,
                "failed_records": 0,
                "dlq_records": 0,
            }
