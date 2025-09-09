import asyncio
import json
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.ingestion_service import IngestionService
from app.models.tm2_data import RawTM2Record, TransformedTM2Record
from app.core.config import Settings
from app.services.mongo_service import MongoService
from app.services.openmrs_client import OpenMRSClient


@pytest.fixture
def settings():
    return Settings()


@pytest.fixture
def mongo_service():
    mongo = MagicMock(spec=MongoService)
    mongo.upsert_record = AsyncMock(return_value=True)
    mongo.log_audit_event = AsyncMock()
    mongo.compute_idempotency_key = MagicMock(return_value="test-key")
    return mongo


@pytest.fixture
def openmrs_client():
    client = MagicMock(spec=OpenMRSClient)
    client.submit_tm2_record = AsyncMock(return_value=True)
    return client


@pytest.fixture
def ingestion_service(settings, mongo_service, openmrs_client):
    service = IngestionService(settings, mongo_service, openmrs_client)
    # Override mappings to a test dict
    service.mappings = {"test_code": "concept-uuid"}
    return service


@pytest.mark.asyncio
async def test_validate_and_transform(ingestion_service):
    raw_record = {
        "patient_identifier": "123",
        "given_name": "John",
        "family_name": "Doe",
        "gender": "M",
        "birthdate": "1980-01-01",
        "encounter_datetime": "2023-01-01T12:00:00",
        "location_uuid": "loc-uuid",
        "provider_uuid": "prov-uuid",
        "tm2_code": "test_code",
        "value_numeric": 42,
        "value_text": None,
        "value_coded": None,
    }
    transformed = await ingestion_service._validate_and_transform(raw_record)
    assert isinstance(transformed, TransformedTM2Record)
    assert transformed.patient_identifier == "123"
    assert transformed.openmrs_concept_uuid == "concept-uuid"
    assert transformed.value_numeric == 42
    assert transformed.idempotency_key == "test-key"


@pytest.mark.asyncio
async def test_ingest_from_file(tmp_path, ingestion_service, mongo_service):
    # Create a test CSV file
    csv_content = "patient_identifier,given_name,family_name,gender,birthdate,encounter_datetime,location_uuid,provider_uuid,tm2_code,value_numeric,value_text,value_coded\n"
    csv_content += "123,John,Doe,M,1980-01-01,2023-01-01T12:00:00,loc-uuid,prov-uuid,test_code,42,,\n"
    file_path = tmp_path / "test.csv"
    file_path.write_text(csv_content)

    stats = await ingestion_service.ingest_from_file(file_path)
    assert stats["total_read"] == 1
    assert stats["valid_records"] == 1
    assert stats["persisted_records"] == 1
    assert stats["invalid_records"] == 0
    assert stats["errors"] == []
    mongo_service.upsert_record.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_from_file_missing_file(ingestion_service):
    with pytest.raises(FileNotFoundError):
        await ingestion_service.ingest_from_file(Path("nonexistent.csv"))
