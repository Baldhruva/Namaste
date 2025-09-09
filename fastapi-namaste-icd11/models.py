from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class GenderEnum(str, Enum):
    male = "male"
    female = "female"
    other = "other"
    unknown = "unknown"


class Patient(BaseModel):
    id: Optional[int] = Field(default=None, description="Auto-incremented ID")
    name: str
    age: int = Field(ge=0, le=130)
    gender: GenderEnum
    diagnosis: Optional[str] = None
    icd11_code: Optional[str] = None
    namaste_code: Optional[str] = None


class DiagnosisRequest(BaseModel):
    keyword: str = Field(min_length=2, description="Symptom or keyword to search ICD-11/TM2")


class MappingRequest(BaseModel):
    namaste_code: str = Field(min_length=2, description="NAMASTE morbidity code to map to ICD-11")


# Minimal FHIR Patient + Condition Bundle mock
class FHIRIdentifier(BaseModel):
    system: Optional[str] = None
    value: str


class FHIRHumanName(BaseModel):
    use: Optional[str] = None
    text: Optional[str] = None
    family: Optional[str] = None
    given: Optional[List[str]] = None


class FHIRCodeableConcept(BaseModel):
    coding: Optional[List[Dict[str, Any]]] = None
    text: Optional[str] = None


class FHIRCondition(BaseModel):
    resourceType: str = "Condition"
    code: FHIRCodeableConcept
    subject: Dict[str, Any]


class FHIRPatient(BaseModel):
    resourceType: str = "Patient"
    id: Optional[str] = None
    identifier: Optional[List[FHIRIdentifier]] = None
    name: Optional[List[FHIRHumanName]] = None
    gender: Optional[str] = None
    birthDate: Optional[str] = None


class FHIRResource(BaseModel):
    resourceType: str = Field("Bundle")
    type: str = "collection"
    entry: List[Dict[str, Any]]
