from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from logging.handlers import RotatingFileHandler
import time
import os

try:
    # These imports will succeed once corresponding files are created
    from routes.icd11 import router as icd11_router
    from routes.namaste import router as namaste_router
    from routes.ehr import router as ehr_router
    from routes.patients import router as patients_router
    from routes.analytics import router as analytics_router
    from auth.auth import router as auth_router
    from config import Settings
except Exception:  # pragma: no cover - during initial scaffold
    icd11_router = None
    namaste_router = None
    ehr_router = None
    patients_router = None
    analytics_router = None
    auth_router = None
    Settings = None


app = FastAPI(
    title="FastAPI NAMASTE-ICD11 EMR",
    version="1.0.0",
    description=(
        "FHIR-compliant EMR integration with NAMASTE and ICD-11 (including TM2).\n"
        "Endpoints: /search_icd11, /map_namaste, /ehr_integration, /patients (CRUD), /analytics, /auth/login"
    ),
)

# Configure settings and CORS
if Settings:
    settings = Settings()
    allowed_origins = settings.CORS_ORIGINS
else:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Logging configuration and request timing middleware
logger = logging.getLogger("app")
if not logger.handlers:
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Console handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # File handler (rotating)
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "app.log"), maxBytes=1_000_000, backupCount=3
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        f"%s %s -> %s in %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/health", tags=["system"])  # simple health endpoint
async def health_check():
    return {"status": "ok"}


# Register routers once modules exist
if icd11_router:
    app.include_router(icd11_router, tags=["icd11"])
if namaste_router:
    app.include_router(namaste_router, tags=["namaste"])
if ehr_router:
    app.include_router(ehr_router, tags=["ehr"])
if patients_router:
    app.include_router(patients_router, tags=["patients"])
if analytics_router:
    app.include_router(analytics_router, tags=["analytics"])
if auth_router:
    app.include_router(auth_router, tags=["auth"])


# Custom error handlers
@app.exception_handler(404)
async def not_found_handler(_, __):
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


@app.exception_handler(422)
async def validation_error_handler(_, exc):
    return JSONResponse(status_code=422, content={"detail": "Validation Error", "errors": str(exc)})


# Note: Run using `uvicorn main:app --reload` from the fastapi-namaste-icd11 directory.
