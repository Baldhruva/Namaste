# FastAPI NAMASTE-ICD11 EMR (FHIR-compliant)

A fully functional FastAPI project integrating NAMASTE and ICD-11 (including Traditional Medicine Module 2 – TM2) into EMR/EHR systems aligned with FHIR principles.

## Features
- ICD-11 + TM2 keyword search (`/search_icd11`)
- NAMASTE → ICD-11 code mapping (`/map_namaste`)
- EHR integration endpoint storing data and returning minimal FHIR Bundle (`/ehr_integration`)
- Patients CRUD with pagination and filtering (`/patients`)
- Analytics (`/analytics`)
- JWT auth (`/auth/login`) protecting sensitive endpoints
- CORS, logging, error handling
- Pytest tests for core endpoints
- Docker and docker-compose for easy run

## Project Structure
```
fastapi-namaste-icd11/
├── main.py
├── models.py
├── database.py
├── config.py
├── routes/
│   ├── icd11.py
│   ├── namaste.py
│   ├── ehr.py
│   ├── patients.py
│   ├── analytics.py
├── auth/
│   ├── auth.py
│   ├── jwt_handler.py
├── tests/
│   ├── test_main.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Setup

### Local (Python)
1. Create a virtual environment and activate it.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run server from project root:
   ```bash
   uvicorn main:app --reload
   ```
4. Open docs at:
   - Swagger UI: http://localhost:8000/docs
   - Redoc: http://localhost:8000/redoc

### Docker
```bash
docker compose up --build
```

## Authentication
- Token URL: `/auth/login`
- Demo user: `admin` / `admin123`
- Add header `Authorization: Bearer <token>` for protected endpoints.

## Example Requests
- Search ICD-11:
  `GET /search_icd11?keyword=diabetes`
- Map NAMASTE:
  `POST /map_namaste` with body `{ "namaste_code": "NAM-AYU-001" }`
- Create Patient (protected):
  `POST /patients/` with body `{ "name": "John", "age": 45, "gender": "male" }`
- EHR Integration (protected):
  `POST /ehr_integration` with patient fields; returns FHIR Bundle

## Notes
- In-memory database is used for demo. `database.py` contains placeholders to add a SQL DB later.
- Mock datasets for ICD-11/TM2 and NAMASTE are included for demo purposes only.

## Testing
```bash
pytest -q
```
