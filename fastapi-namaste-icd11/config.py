import os
from typing import List, Optional


class Settings:
    def __init__(self) -> None:
        self.APP_NAME: str = "FastAPI NAMASTE-ICD11 EMR"

        cors_origins = os.getenv("CORS_ORIGINS", "*")
        self.CORS_ORIGINS: List[str] = [o.strip() for o in cors_origins.split(",")] if cors_origins else ["*"]

        # JWT
        self.JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "supersecretkey_change_me")
        self.JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

        # DB hook (for future extension)
        self.DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
