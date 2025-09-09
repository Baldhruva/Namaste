from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel
from .jwt_handler import create_access_token, decode_access_token
from config import Settings

router = APIRouter(prefix="/auth")
settings = Settings()

# Simple in-memory user store for demo
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_fake_user_db = {
    "admin": {
        "username": "admin",
        # password: admin123
        "hashed_password": pwd_context.hash("admin123"),
    }
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def authenticate_user(username: str, password: str) -> bool:
    user = _fake_user_db.get(username)
    if not user:
        return False
    return verify_password(password, user["hashed_password"])


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if not authenticate_user(form_data.username, form_data.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(subject=form_data.username, expires_delta=access_token_expires)
    return TokenResponse(access_token=token)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    return decode_access_token(token)
