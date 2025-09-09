"""
OpenMRS REST API Client

Handles communication with OpenMRS REST API including:
- Authentication and session management
- Resilient HTTP requests with retries and backoff
- Patient creation and encounter submission
- Error handling and logging
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..core.config import Settings

logger = logging.getLogger(__name__)


class OpenMRSClient:
    """Client for OpenMRS REST API with resilience and authentication."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = str(settings.openmrs.base_url) if settings.openmrs.base_url else None
        self.username = settings.openmrs.username
        self.password = settings.openmrs.password
        self.timeout = settings.openmrs.timeout_seconds
        self.max_retries = settings.openmrs.max_retries
        self.backoff_base = settings.openmrs.backoff_base
        self.backoff_max = settings.openmrs.backoff_max
        self.create_patients = settings.openmrs.create_patients

        # HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )

        self._session_token: Optional[str] = None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def _authenticate(self) -> Optional[str]:
        """Authenticate with OpenMRS and return session token."""
        if not self.base_url or not self.username or not self.password:
            logger.warning("openmrs_auth_skipped", reason="missing_credentials")
            return None

        auth_url = f"{self.base_url}/session"
        auth_data = {"username": self.username, "password": self.password}

        try:
            response = await self.client.post(auth_url, json=auth_data)
            response.raise_for_status()
            session_data = response.json()

            if session_data.get("authenticated"):
                self._session_token = response.cookies.get("JSESSIONID")
                logger.info("openmrs_auth_success")
                return self._session_token
            else:
                logger.error("openmrs_auth_failed", error="invalid_credentials")
                return None

        except httpx.HTTPError as e:
            logger.error("openmrs_auth_error", error=str(e))
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=8.0),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ConnectError)),
    )
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an authenticated request to OpenMRS API with retry logic."""
        if not self.base_url:
            raise ValueError("OpenMRS base URL not configured")

        url = f"{self.base_url}{endpoint}"

        # Add session cookie if available
        if self._session_token:
            cookies = kwargs.get("cookies", {})
            cookies["JSESSIONID"] = self._session_token
            kwargs["cookies"] = cookies

        # Add JSON content type for POST/PUT
        if method.upper() in ("POST", "PUT", "PATCH"):
            headers = kwargs.get("headers", {})
            headers["Content-Type"] = "application/json"
            kwargs["headers"] = headers

        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                # Try to re-authenticate once
                logger.warning("openmrs_unauthorized", endpoint=endpoint)
                self._session_token = None
                await self._authenticate()
                if self._session_token:
                    # Retry with new token
                    cookies = kwargs.get("cookies", {})
                    cookies["JSESSIONID"] = self._session_token
                    kwargs["cookies"] = cookies
                    response = await self.client.request(method, url, **kwargs)
                    response.raise_for_status()
                    return response.json() if response.content else {}
                else:
                    raise
            else:
                logger.error("openmrs_http_error", status_code=e.response.status_code, endpoint=endpoint, response=e.response.text)
                raise

        except httpx.RequestError as e:
            logger.error("openmrs_request_error", error=str(e), endpoint=endpoint)
            raise

    async def create_patient(self, patient_data: Dict[str, Any]) -> Optional[str]:
        """Create a patient in OpenMRS. Returns patient UUID if successful."""
        if not self.create_patients:
            logger.info("openmrs_patient_creation_disabled")
            return None

        try:
            # Ensure we have a session
            if not self._session_token:
                await self._authenticate()

            result = await self._make_request("POST", "/ws/rest/v1/patient", json=patient_data)
            patient_uuid = result.get("uuid")
            logger.info("openmrs_patient_created", patient_uuid=patient_uuid)
            return patient_uuid

        except Exception as e:
            logger.error("openmrs_patient_creation_error", error=str(e), patient_data=patient_data)
            return None

    async def create_encounter(self, encounter_data: Dict[str, Any]) -> Optional[str]:
        """Create an encounter in OpenMRS. Returns encounter UUID if successful."""
        try:
            # Ensure we have a session
            if not self._session_token:
                await self._authenticate()

            result = await self._make_request("POST", "/ws/rest/v1/encounter", json=encounter_data)
            encounter_uuid = result.get("uuid")
            logger.info("openmrs_encounter_created", encounter_uuid=encounter_uuid)
            return encounter_uuid

        except Exception as e:
            logger.error("openmrs_encounter_creation_error", error=str(e), encounter_data=encounter_data)
            return None

    async def create_observation(self, obs_data: Dict[str, Any]) -> Optional[str]:
        """Create an observation in OpenMRS. Returns observation UUID if successful."""
        try:
            # Ensure we have a session
            if not self._session_token:
                await self._authenticate()

            result = await self._make_request("POST", "/ws/rest/v1/obs", json=obs_data)
            obs_uuid = result.get("uuid")
            logger.info("openmrs_observation_created", obs_uuid=obs_uuid)
            return obs_uuid

        except Exception as e:
            logger.error("openmrs_observation_creation_error", error=str(e), obs_data=obs_data)
            return None

    async def submit_tm2_record(self, record: Dict[str, Any], patient_uuid: Optional[str] = None) -> bool:
        """Submit a TM2 record to OpenMRS. Returns True if successful."""
        try:
            # If no patient UUID provided and patient creation is enabled, create patient first
            if not patient_uuid and self.create_patients:
                patient_data = self._build_patient_data(record)
                patient_uuid = await self.create_patient(patient_data)

            if not patient_uuid:
                logger.warning("openmrs_submission_skipped", reason="no_patient_uuid", record=record)
                return False

            # Create encounter
            encounter_data = self._build_encounter_data(record, patient_uuid)
            encounter_uuid = await self.create_encounter(encounter_data)

            if not encounter_uuid:
                return False

            # Create observation
            obs_data = self._build_observation_data(record, patient_uuid, encounter_uuid)
            obs_uuid = await self.create_observation(obs_data)

            return obs_uuid is not None

        except Exception as e:
            logger.error("openmrs_record_submission_error", error=str(e), record=record)
            return False

    def _build_patient_data(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Build patient data from TM2 record."""
        return {
            "identifiers": [
                {
                    "identifier": record.get("patient_identifier"),
                    "identifierType": "05a29f94-c0ed-11e2-94be-8c13b969e334",  # OpenMRS ID
                    "location": record.get("location_uuid", "8d6c993e-c2cc-11de-8d13-0010c6dffd0f"),  # Unknown Location
                    "preferred": True,
                }
            ],
            "person": {
                "names": [
                    {
                        "givenName": record.get("given_name", ""),
                        "familyName": record.get("family_name", ""),
                    }
                ],
                "gender": record.get("gender", "U"),
                "birthdate": record.get("birthdate"),
                "birthdateEstimated": False,
            },
        }

    def _build_encounter_data(self, record: Dict[str, Any], patient_uuid: str) -> Dict[str, Any]:
        """Build encounter data from TM2 record."""
        return {
            "patient": patient_uuid,
            "encounterType": "8d5b27bc-c2cc-11de-8d13-0010c6dffd0f",  # Visit Note
            "encounterDatetime": record.get("encounter_datetime"),
            "location": record.get("location_uuid", "8d6c993e-c2cc-11de-8d13-0010c6dffd0f"),  # Unknown Location
            "provider": record.get("provider_uuid", "c2299800-cca9-11e0-9572-0800200c9a66"),  # Super User
        }

    def _build_observation_data(self, record: Dict[str, Any], patient_uuid: str, encounter_uuid: str) -> Dict[str, Any]:
        """Build observation data from TM2 record."""
        # Map TM2 code to OpenMRS concept UUID (this would use the mappings file)
        concept_uuid = record.get("openmrs_concept_uuid", "8d4a4c94-c2cc-11de-8d13-0010c6dffd0f")  # Default concept

        obs_data = {
            "person": patient_uuid,
            "obsDatetime": record.get("encounter_datetime"),
            "concept": concept_uuid,
            "encounter": encounter_uuid,
        }

        # Set the value based on the type
        if "value_numeric" in record:
            obs_data["value"] = record["value_numeric"]
        elif "value_text" in record:
            obs_data["value"] = record["value_text"]
        elif "value_coded" in record:
            obs_data["value"] = record["value_coded"]

        return obs_data
