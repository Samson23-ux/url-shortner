import json
import base64
from uuid import uuid4
from typing import Optional
from jose import jwt, JWTError
from binascii import Error as binascii_error
from pwdlib.hashers.argon2 import Argon2Hasher
from datetime import datetime, timezone, timedelta


from app.core.config import get_settings
from app.api.schemas.auth import TokenData


settings = get_settings()
arg2_hasher = Argon2Hasher()


async def encode_cursor(payload: dict) -> str:
    payload_string: str = json.dumps(payload)
    return base64.b64encode(payload_string.encode()).decode()


async def decode_cursor(cursor_string: str, curr_order: str) -> dict:
    try:
        cursor_string = base64.b64decode(cursor_string)
        cursor_payload = json.loads(cursor_string)

        if cursor_payload["order"] != curr_order.lower():
            return None
        return cursor_payload
    except (json.JSONDecodeError, UnicodeDecodeError, binascii_error):
        return None


async def hash_password(password: str) -> str:
    password: str = password + settings.ARGON2_PASSWORD_PEPPER
    return arg2_hasher.hash(password)


async def verify_password(password: str, hash_password: str) -> bool:
    password: str = password + settings.ARGON2_PASSWORD_PEPPER
    return arg2_hasher.verify(password, hash_password)


async def create_access_token(
    token_data: TokenData, expire_time: Optional[int] = None
) -> str:
    if not expire_time:
        expire_time: datetime = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_TIME
        )
    else:
        expire_time: datetime = datetime.now(timezone.utc) + timedelta(
            minutes=expire_time
        )

    payload: dict = {
        "sub": token_data.email,
        "exp": expire_time,
        "iat": datetime.now(timezone.utc),
    }

    token: str = jwt.encode(
        claims=payload,
        key=settings.ACCESS_TOKEN_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    return token


async def create_refresh_token(
    token_data: TokenData, expire_time: Optional[int] = None
) -> tuple:
    if not expire_time:
        expire_time: datetime = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_TIME
        )
    else:
        expire_time: datetime = datetime.now(timezone.utc) + timedelta(
            minutes=expire_time
        )

    payload: dict = {
        "sub": token_data.email,
        "exp": expire_time,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid4()),
    }

    token: str = jwt.encode(
        claims=payload,
        key=settings.REFRESH_TOKEN_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    return token, payload["jti"], expire_time


async def decode_token(token: str, key: str):
    try:
        payload: dict = jwt.decode(
            token=token, key=key, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None
