from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Optional
from models import Patient
from database import db
from auth.auth import get_current_user

router = APIRouter(prefix="/patients")


@router.post("/", dependencies=[Depends(get_current_user)])
async def create_patient(patient: Patient) -> Dict:
    created = db.create_patient(patient.dict(exclude_unset=True))
    return created


@router.get("/")
async def list_patients(skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100), gender: Optional[str] = None) -> List[Dict]:
    return db.list_patients(skip=skip, limit=limit, gender=gender)


@router.get("/{patient_id}")
async def get_patient(patient_id: int) -> Dict:
    patient = db.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.put("/{patient_id}", dependencies=[Depends(get_current_user)])
async def update_patient(patient_id: int, updates: Patient) -> Dict:
    updated = db.update_patient(patient_id, updates.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Patient not found")
    return updated


@router.delete("/{patient_id}", dependencies=[Depends(get_current_user)])
async def delete_patient(patient_id: int) -> Dict:
    ok = db.delete_patient(patient_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"deleted": True}
