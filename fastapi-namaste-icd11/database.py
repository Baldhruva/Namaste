from typing import List, Dict, Optional
from threading import Lock

# Mock datasets (5–10 examples each)
# ICD-11 including TM2 (Traditional Medicine Module 2) examples
ICD11_DATA: List[Dict[str, str]] = [
    {"code": "1A00", "title": "Cholera", "module": "ICD-11"},
    {"code": "5A11", "title": "Type 2 diabetes mellitus", "module": "ICD-11"},
    {"code": "MG30.0", "title": "Migraine without aura", "module": "ICD-11"},
    {"code": "RA01", "title": "Acute nasopharyngitis [common cold]", "module": "ICD-11"},
    {"code": "TM2-XY01", "title": "Qi deficiency pattern", "module": "TM2"},
    {"code": "TM2-XY02", "title": "Blood stasis pattern", "module": "TM2"},
    {"code": "TM2-XY03", "title": "Liver qi stagnation pattern", "module": "TM2"},
    {"code": "TM2-XY04", "title": "Damp-heat pattern", "module": "TM2"},
    {"code": "TM2-XY05", "title": "Kidney yin deficiency pattern", "module": "TM2"},
]

# NAMASTE morbidity codes (mock)
NAMASTE_DATA: List[Dict[str, str]] = [
    {"code": "NAM-AYU-001", "title": "Prameha (Diabetes)"},
    {"code": "NAM-AYU-002", "title": "Jwara (Fever)"},
    {"code": "NAM-AYU-003", "title": "Shirashoola (Headache)"},
    {"code": "NAM-AYU-004", "title": "Kasa (Cough)"},
    {"code": "NAM-AYU-005", "title": "Pandu (Anemia)"},
    {"code": "NAM-SID-006", "title": "Neerizhivu (Diabetes)"},
    {"code": "NAM-UNA-007", "title": "Dawali (Varicose veins)"},
]

# Mock mapping between NAMASTE and ICD-11
NAMASTE_TO_ICD11: Dict[str, str] = {
    "NAM-AYU-001": "5A11",  # Diabetes
    "NAM-AYU-002": "RA01",  # Fever -> common cold (approximation)
    "NAM-AYU-003": "MG30.0",  # Headache -> Migraine without aura (approx)
    "NAM-AYU-004": "RA01",  # Cough -> common cold (approx)
    "NAM-AYU-005": "3A00",  # Anemia (example; 3A00 is placeholder for demo)
    "NAM-SID-006": "5A11",  # Diabetes
}


# In-memory patient storage
class InMemoryDB:
    def __init__(self):
        self._patients: Dict[int, Dict] = {}
        self._id_counter = 1
        self._lock = Lock()

    def create_patient(self, patient: Dict) -> Dict:
        with self._lock:
            patient_id = self._id_counter
            self._id_counter += 1
            patient["id"] = patient_id
            self._patients[patient_id] = patient
            return patient

    def get_patient(self, patient_id: int) -> Optional[Dict]:
        return self._patients.get(patient_id)

    def list_patients(self, skip: int = 0, limit: int = 10, gender: Optional[str] = None) -> List[Dict]:
        items = list(self._patients.values())
        if gender:
            items = [p for p in items if p.get("gender") == gender]
        return items[skip: skip + limit]

    def update_patient(self, patient_id: int, updates: Dict) -> Optional[Dict]:
        if patient_id not in self._patients:
            return None
        self._patients[patient_id].update(updates)
        return self._patients[patient_id]

    def delete_patient(self, patient_id: int) -> bool:
        return self._patients.pop(patient_id, None) is not None

    def stats(self) -> Dict[str, int]:
        return {"patients": len(self._patients)}


db = InMemoryDB()


# Hooks/placeholders to extend to SQL DB later
# def get_session():
#     """Return SQLAlchemy session using DATABASE_URL from settings."""
#     ...
