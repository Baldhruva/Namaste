import json
from typing import Any, Dict, List

import httpx
import structlog

from core.config import Settings
from models.icd_models import ICDEntity
from services.mongo_service import MongoService

logger = structlog.get_logger()


class ICDService:
    def __init__(self, settings: Settings, mongo: MongoService):
        self.settings = settings
        self.mongo = mongo
        self.client = httpx.AsyncClient(timeout=self.settings.REQUEST_TIMEOUT_SECONDS)

    async def close(self):
        await self.client.aclose()

    async def search(self, q: str, module: str, limit: int) -> Dict[str, Any]:
        # Compute cache key
        query_hash = self.mongo.compute_query_hash(q, module, limit)

        # Attempt cache fetch
        cached = await self.mongo.get_cached_response(query_hash, module)
        if cached and "data" in cached:
            data = cached["data"]
            # ensure count limited
            data["results"] = data.get("results", [])[:limit]
            data["source"] = "CACHE"
            data["query_hash"] = query_hash
            data["cached_at"] = cached.get("created_at")
            return data

        # On cache miss, call WHO API
        url = self.settings.WHO_MMS_SEARCH_URL if module == "MMS" else self.settings.WHO_TM2_SEARCH_URL
        headers = {"Accept": "application/json"}
        if self.settings.WHO_API_KEY:
            headers["API-Version"] = "v2"
            headers["Authorization"] = f"Bearer {self.settings.WHO_API_KEY}"

        params = {
            "q": q,
            "flatResults": "true",
            "limit": str(limit),
        }

        try:
            resp = await self.client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPError as e:
            logger.warning("who_api_error", error=str(e), module=module)
            # Return empty result gracefully
            payload = {"destinations": []}

        results = self._transform_results(payload)
        data = {
            "source": "WHO_MMS" if module == "MMS" else "WHO_TM2",
            "query_hash": query_hash,
            "count": len(results),
            "results": results[:limit],
        }

        # Write to cache (best-effort)
        await self.mongo.set_cached_response(query_hash, module, data)
        return data

    def _transform_results(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        # The WHO API schema varies. We'll try to normalize common fields.
        items: List[Dict[str, Any]] = []
        # WHO responses may contain 'destinationEntities' or 'items' depending on endpoint
        raw_items = (
            payload.get("destinationEntities")
            or payload.get("items")
            or payload.get("results")
            or []
        )
        for it in raw_items:
            code = it.get("code") or it.get("theCode") or it.get("id") or ""
            title = (
                (it.get("title") or it.get("titleSynonym") or {}).get("@value")
                if isinstance(it.get("title"), dict)
                else it.get("title")
            ) or it.get("label") or ""
            definition = (
                (it.get("definition") or {}).get("@value")
                if isinstance(it.get("definition"), dict)
                else it.get("definition")
            )

            # Strictly avoid PHI: we only keep code/title/definition
            items.append(ICDEntity(code=str(code), title=str(title or ""), definition=(str(definition) if definition else None)).model_dump())
        return items
