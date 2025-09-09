from fastapi import APIRouter, HTTPException, Query
from typing import List
from database import ICD11_DATA
from models import DiagnosisRequest

router = APIRouter()


@router.get("/search_icd11")
async def search_icd11(keyword: str = Query(..., min_length=2)) -> List[dict]:
    term = keyword.lower()
    results = [item for item in ICD11_DATA if term in item["title"].lower() or term in item["code"].lower()]
    if not results:
        raise HTTPException(status_code=404, detail="No ICD-11/TM2 codes found for the given keyword")
    return results
