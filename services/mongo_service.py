import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import motor.motor_asyncio
from pymongo import ASCENDING
from pymongo.errors import PyMongoError

from core.config import Settings


class MongoService:
    """Encapsulates MongoDB interactions: caching, application logs, audit trails.

    Collections:
      - cached_responses: stores cached search results with TTL
      - application_logs: structured application logs (no PHI)
      - audit_trails: minimal audit events (no PHI)
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
        self.db = None
        self.cached_responses = None
        self.application_logs = None
        self.audit_trails = None
        self.enabled: bool = False

    async def init(self) -> None:
        try:
            self.client = motor.motor_asyncio.AsyncIOMotorClient(
                self.settings.MONGODB_URI, uuidRepresentation="standard"
            )
            self.db = self.client[self.settings.MONGODB_DB_NAME]
            self.cached_responses = self.db["cached_responses"]
            self.application_logs = self.db["application_logs"]
            self.audit_trails = self.db["audit_trails"]

            # TTL index for cached responses
            # Document schema: { _id, query_hash, module, data, created_at }
            await self.cached_responses.create_index(
                [("query_hash", ASCENDING), ("module", ASCENDING)], unique=True
            )
            await self.cached_responses.create_index(
                "created_at", expireAfterSeconds=int(self.settings.CACHE_TTL_SECONDS)
            )

            # Basic indexes for logs and audits
            await self.application_logs.create_index([("timestamp", ASCENDING)])
            await self.audit_trails.create_index([("timestamp", ASCENDING)])

            self.enabled = True
        except Exception:
            # Degraded mode: disable DB-backed features if connection/indexing fails
            self.enabled = False

    async def close(self) -> None:
        if self.client:
            self.client.close()

    # ---------------------- Caching ----------------------
    @staticmethod
    def compute_query_hash(q: str, module: str, limit: int) -> str:
        normalized = f"{q.strip().lower()}|{module}|{int(limit)}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    async def get_cached_response(self, query_hash: str, module: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        try:
            doc = await self.cached_responses.find_one({"query_hash": query_hash, "module": module})
            return doc
        except PyMongoError:
            # Fail gracefully on cache read errors
            return None

    async def set_cached_response(self, query_hash: str, module: str, data: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        try:
            await self.cached_responses.update_one(
                {"query_hash": query_hash, "module": module},
                {
                    "$set": {
                        "data": data,
                        "created_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
        except PyMongoError:
            # Ignore write errors to not impact main flow
            pass

    # ---------------------- Logging ----------------------
    async def log(self, level: str, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Persist application log without PHI."""
        if not self.enabled:
            return
        try:
            await self.application_logs.insert_one(
                {
                    "level": level,
                    "message": message,
                    "extra": extra or {},
                    "timestamp": datetime.now(timezone.utc),
                }
            )
        except PyMongoError:
            pass

    # ---------------------- Audit ----------------------
    async def audit(self, action: str, module: str, query_hash: str, requester_ip: Optional[str]) -> None:
        if not self.enabled:
            return
        try:
            await self.audit_trails.insert_one(
                {
                    "action": action,
                    "module": module,
                    "query_hash": query_hash,
                    "requester_ip": requester_ip,
                    "timestamp": datetime.now(timezone.utc),
                }
            )
        except PyMongoError:
            pass
