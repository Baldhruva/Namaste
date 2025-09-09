from fastapi import APIRouter, HTTPException
from typing import Dict
from models import MappingRequest
from database import NAMASTE_TO_ICD11, NAMASTE_DATA

router = APIRouter()


@router.post("/map_namaste")
async def map_namaste(body: MappingRequest) -> Dict[str, str]:
    code = body.namaste_code
    # Verify NAMASTE code exists (case-insensitive)
    if not any(x["code"].lower() == code.lower() for x in NAMASTE_DATA):
        raise HTTPException(status_code=404, detail="NAMASTE code not found")
    # Map using case-sensitive dict; try direct then normalized
    icd = NAMASTE_TO_ICD11.get(code) or NAMASTE_TO_ICD11.get(code.upper()) or NAMASTE_TO_ICD11.get(code.lower())
    if not icd:
        raise HTTPException(status_code=404, detail="No ICD-11 mapping available for the given NAMASTE code")
    return {"namaste_code": code, "icd11_code": icd}
