from fastapi import APIRouter
from typing import Dict
from collections import Counter
from database import db

router = APIRouter()


@router.get("/analytics")
async def analytics() -> Dict:
    # Basic stats from in-memory DB
    patients = db.list_patients(skip=0, limit=10_000)
    total = len(patients)
    diagnoses = [p.get("diagnosis") for p in patients if p.get("diagnosis")]
    common = Counter(diagnoses).most_common(5)
    mapping_success = sum(1 for p in patients if p.get("namaste_code") and p.get("icd11_code"))
    mapping_rate = (mapping_success / total) * 100 if total else 0
    return {
        "total_patients": total,
        "common_conditions": common,
        "mapping_success_rate": round(mapping_rate, 2),
    }
