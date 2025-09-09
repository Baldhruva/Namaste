"""
Ingestion Service

Implements the TM2 data ingestion pipeline:
- Reader: Streams TM2 dataset files (CSV/JSON)
- Validator: Validates records using Pydantic models
- Transformer: Normalizes data, maps TM2 codes to OpenMRS concepts, computes idempotency keys
- Persistence: Stores transformed records in MongoDB
- Submission: Submits pending records to OpenMRS API
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import uuid4

import ijson
from pydantic import ValidationError

from ..core.config import Settings
from ..core.logging import bind_context, hash_identifier
from ..models.tm2_data import RawTM2Record, TransformedTM2Record
from .mongo_service import MongoService
from .openmrs_client import OpenMRSClient

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting TM2 data from files and submitting to OpenMRS."""

    def __init__(self, settings: Settings, mongo_service: MongoService, openmrs_client: OpenMRSClient):
        self.settings = settings
        self.mongo = mongo_service
        self.openmrs = openmrs_client
        self.mappings = self._load_mappings()

    def _load_mappings(self) -> Dict[str, str]:
        """Load TM2 to OpenMRS concept mappings from file."""
        mappings_path = Path(self.settings.ingestion.mappings_path)
        if not mappings_path.exists():
            logger.warning("mappings_file_not_found: %s", str(mappings_path))
            return {}

        try:
            with open(mappings_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error("mappings_load_error", error=str(e), path=str(mappings_path))
            return {}

    async def ingest_from_file(self, file_path: Optional[Path] = None) -> Dict[str, Any]:
        """Ingest TM2 data from a file. Returns ingestion statistics."""
        if file_path is None:
            # Default to settings.ingestion.data_path which may be a file path
            path_candidate = self.settings.ingestion.data_path
            file_path = Path(path_candidate) if not isinstance(path_candidate, Path) else path_candidate

        if not Path(file_path).exists():
            raise FileNotFoundError(f"Data file not found: {file_path}")

        file_path = Path(file_path)
        if file_path.is_dir():
            raise ValueError(f"Expected a file path but got a directory: {file_path}")

        batch_id = str(uuid4())
        stats = {
            "batch_id": batch_id,
            "total_read": 0,
            "valid_records": 0,
            "invalid_records": 0,
            "persisted_records": 0,
            "errors": [],
        }

        logger.info("ingestion_started", batch_id=batch_id, file_path=str(file_path))

        try:
            async for record in self._read_records(file_path):
                stats["total_read"] += 1

                # Validate and transform
                try:
                    transformed = await self._validate_and_transform(record)
                    stats["valid_records"] += 1

                    # Persist to MongoDB
                    persisted = await self.mongo.upsert_record(transformed.model_dump(), batch_id)
                    if persisted:
                        stats["persisted_records"] += 1

                except ValidationError as e:
                    stats["invalid_records"] += 1
                    error_msg = f"Validation error: {e}"
                    stats["errors"].append(error_msg)
                    logger.warning("record_validation_error", batch_id=batch_id, error=error_msg, record=record)

                except Exception as e:
                    stats["invalid_records"] += 1
                    error_msg = f"Processing error: {str(e)}"
                    stats["errors"].append(error_msg)
                    logger.error("record_processing_error", batch_id=batch_id, error=error_msg, record=record)

        except Exception as e:
            logger.error("ingestion_error", batch_id=batch_id, error=str(e))
            stats["errors"].append(f"Ingestion failed: {str(e)}")

        # Log audit event
        await self.mongo.log_audit_event("ingestion_completed", stats, batch_id)

        logger.info("ingestion_completed", **stats)
        return stats

    async def submit_pending_records(self, limit: int = 100) -> Dict[str, Any]:
        """Submit pending records to OpenMRS. Returns submission statistics."""
        batch_id = str(uuid4())
        stats = {
            "batch_id": batch_id,
            "attempted": 0,
            "successful": 0,
            "failed": 0,
            "errors": [],
        }

        logger.info("submission_started", batch_id=batch_id)

        pending_records = await self.mongo.get_pending_records(limit)

        for record_doc in pending_records:
            stats["attempted"] += 1
            record = record_doc["data"]
            idempotency_key = record_doc["idempotency_key"]

            try:
                # Submit to OpenMRS
                success = await self.openmrs.submit_tm2_record(record)

                if success:
                    stats["successful"] += 1
                    await self.mongo.mark_submitted(idempotency_key, True)
                    logger.info("record_submitted", batch_id=batch_id, idempotency_key=idempotency_key)
                else:
                    stats["failed"] += 1
                    error_msg = "OpenMRS submission failed"
                    stats["errors"].append(error_msg)
                    await self.mongo.mark_submitted(idempotency_key, False, error_msg)
                    logger.warning("record_submission_failed", batch_id=batch_id, idempotency_key=idempotency_key, error=error_msg)

            except Exception as e:
                stats["failed"] += 1
                error_msg = f"Submission error: {str(e)}"
                stats["errors"].append(error_msg)
                await self.mongo.mark_submitted(idempotency_key, False, error_msg)
                logger.error("record_submission_error", batch_id=batch_id, idempotency_key=idempotency_key, error=str(e))

                # Move to DLQ if max retries exceeded
                if stats["failed"] > 3:  # Simple retry logic
                    await self.mongo.move_to_dlq(record, error_msg, batch_id)

        # Log audit event
        await self.mongo.log_audit_event("submission_completed", stats, batch_id)

        logger.info("submission_completed", **stats)
        return stats

    async def _read_records(self, file_path: Path) -> AsyncGenerator[Dict[str, Any], None]:
        """Read records from file in streaming fashion."""
        file_format = self._detect_format(file_path)

        if file_format == "csv":
            async for record in self._read_csv(file_path):
                yield record
        elif file_format == "ndjson":
            async for record in self._read_ndjson(file_path):
                yield record
        elif file_format == "json":
            async for record in self._read_json_array(file_path):
                yield record
        else:
            raise ValueError(f"Unsupported file format: {file_format}")

    def _detect_format(self, file_path: Path) -> str:
        """Detect file format based on extension or content."""
        if file_path.suffix.lower() == ".csv":
            return "csv"
        elif file_path.suffix.lower() in (".json", ".ndjson", ".jsonl"):
            return "ndjson" if file_path.suffix.lower() in (".ndjson", ".jsonl") else "json"
        else:
            return self.settings.ingestion.default_format

    async def _read_csv(self, file_path: Path) -> AsyncGenerator[Dict[str, Any], None]:
        """Read CSV file records."""
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield row

    async def _read_ndjson(self, file_path: Path) -> AsyncGenerator[Dict[str, Any], None]:
        """Read NDJSON file records."""
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)

    async def _read_json_array(self, file_path: Path) -> AsyncGenerator[Dict[str, Any], None]:
        """Read JSON array file records."""
        with open(file_path, "rb") as f:
            for record in ijson.items(f, "item"):
                yield record

    async def _validate_and_transform(self, raw_record: Dict[str, Any]) -> TransformedTM2Record:
        """Validate raw record and transform to normalized format."""
        # Validate raw record
        raw = RawTM2Record(**raw_record)

        # Transform to normalized format
        transformed_data = {
            "patient_identifier": raw.patient_identifier,
            "given_name": raw.given_name,
            "family_name": raw.family_name,
            "gender": raw.gender,
            "birthdate": raw.birthdate.isoformat() if raw.birthdate else None,
            "encounter_datetime": raw.encounter_datetime.isoformat() if raw.encounter_datetime else None,
            "location_uuid": raw.location_uuid,
            "provider_uuid": raw.provider_uuid,
            "tm2_code": raw.tm2_code,
            "openmrs_concept_uuid": self.mappings.get(raw.tm2_code),
        }

        # Add value based on type
        if raw.value_numeric is not None:
            transformed_data["value_numeric"] = raw.value_numeric
        elif raw.value_text:
            transformed_data["value_text"] = raw.value_text
        elif raw.value_coded:
            transformed_data["value_coded"] = raw.value_coded

        # Clean and normalize free text
        if "value_text" in transformed_data:
            transformed_data["value_text"] = self._clean_text(transformed_data["value_text"])

        # Compute idempotency key
        transformed_data["idempotency_key"] = self._compute_idempotency_key(transformed_data)

        return TransformedTM2Record(**transformed_data)

    def _clean_text(self, text: str) -> str:
        """Clean and normalize free text fields."""
        if not text:
            return ""
        # Remove extra whitespace, normalize quotes, etc.
        return " ".join(text.split()).strip()

    def _compute_idempotency_key(self, record: Dict[str, Any]) -> str:
        """Compute idempotency key for the record."""
        # Use same logic as MongoService
        return self.mongo.compute_idempotency_key(record)
