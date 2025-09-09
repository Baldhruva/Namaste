from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, constr


class SearchSource(str):
    WHO_MMS = "WHO_MMS"
    WHO_TM2 = "WHO_TM2"
    CACHE = "CACHE"


class SearchRequest(BaseModel):
    q: constr(strip_whitespace=True, min_length=1, max_length=200) = Field(..., description="Query term")
    module: Literal["MMS", "TM2"] = Field(
        default="MMS", description="ICD module to search: MMS (standard) or TM2 (Traditional Medicine)"
    )
    limit: int = Field(default=10, ge=1, le=50)


class ICDEntity(BaseModel):
    code: str
    title: str
    definition: Optional[str] = None


class SearchResult(BaseModel):
    source: Literal["WHO_MMS", "WHO_TM2", "CACHE"]
    query_hash: str
    count: int
    results: List[ICDEntity]
    cached_at: Optional[datetime] = None


class AuditTrail(BaseModel):
    action: Literal["SEARCH"]
    module: Literal["MMS", "TM2"]
    query_hash: str
    timestamp: datetime
    requester_ip: Optional[str] = None


class AppLog(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    message: str
    extra: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
