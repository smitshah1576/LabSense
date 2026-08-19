import time
from jose import JWTError, jwt
from fastapi import HTTPException, status
from ..config import settings

def create_access_token(data: dict) -> str:
    payload = data.copy()
    expires = time.time() + (settings.JWT_EXPIRY_MINUTES * 60)
    payload.update({"exp": expires})
    encoded_jwt = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict:
    try:
        decoded_token = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return decoded_token if decoded_token.get("exp", 0) >= time.time() else None
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
