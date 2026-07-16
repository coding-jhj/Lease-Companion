"""비밀번호 해시(bcrypt)와 JWT Bearer 토큰 발급·검증."""

import os
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

ALGORITHM = "HS256"
# 로컬 MVP 만료 24h 임시값 — 운영 전 토큰 정책(만료·refresh·폐기) 재검토
ACCESS_TOKEN_TTL = timedelta(hours=24)

# 팀 확정(2026-07-16): Passlib-bcrypt
_pwd_context = CryptContext(schemes=["bcrypt"])


def _jwt_secret() -> str:
    secret = os.environ["JWT_SECRET"]
    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET은 HS256 사용을 위해 32바이트 이상이어야 합니다.")
    return secret


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> int:
    """유효하면 user_id를 반환한다. 무효·만료 토큰이면 jwt.PyJWTError."""
    payload = jwt.decode(token, _jwt_secret(), algorithms=[ALGORITHM])
    return int(payload["sub"])
