from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
from models import Patient, FHIRResource, FHIRPatient, FHIRCondition, FHIRCodeableConcept
from database import db
from auth.auth import get_current_user

router = APIRouter()


@router.post("/ehr_integration", dependencies=[Depends(get_current_user)])
async def ehr_integration(patient: Patient) -> Dict:
    # Save patient record
    created = db.create_patient(patient.dict(exclude_unset=True))

    # Create a minimal FHIR Bundle with Patient + Condition entries
    fhir_patient = FHIRPatient(
        id=str(created["id"]),
        name=[{"text": created["name"]}],
        gender=created.get("gender"),
    )

    # Build coding list with NAMASTE and ICD-11 when present
    coding = []
    if created.get("icd11_code"):
        coding.append({
            "system": "http://id.who.int/icd/release/11/mms",
            "code": created["icd11_code"],
            "display": created.get("diagnosis"),
        })
    if created.get("namaste_code"):
        coding.append({
            "system": "https://namaste-ayush.gov.in/",
            "code": created["namaste_code"],
            "display": created.get("diagnosis"),
        })

    fhir_condition = FHIRCondition(
        code=FHIRCodeableConcept(coding=coding or None, text=created.get("diagnosis")),
        subject={"reference": f"Patient/{created['id']}"},
    )

    bundle = FHIRResource(
        entry=[
            {"resource": fhir_patient.dict()},
            {"resource": fhir_condition.dict()},
        ]
    )

    return {"patient": created, "fhir": bundle.dict()}
