from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from models.icd_models import SearchRequest, SearchResult
from services.icd_service import ICDService

router = APIRouter()


def get_icd_service(request: Request) -> ICDService:
    return request.app.state.icd_service


@router.post("/search", response_model=SearchResult)
async def search_endpoint(payload: SearchRequest, request: Request, icd: ICDService = Depends(get_icd_service)):
    # PHI policy: only process query term; no PHI stored or logged
    data = await icd.search(q=payload.q, module=payload.module, limit=payload.limit)

    # Minimal audit (no PHI)
    mongo = request.app.state.mongo_service
    await mongo.audit(action="SEARCH", module=payload.module, query_hash=data["query_hash"], requester_ip=request.client.host)

    # Return plain dict so FastAPI applies response_model validation/serialization
    return data
