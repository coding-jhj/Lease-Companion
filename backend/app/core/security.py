"""비밀번호 해시(bcrypt)와 JWT Bearer 토큰 발급·검증."""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

ALGORITHM = "HS256"
# ponytail: 만료 24h 임시값 — 토큰 정책(만료·refresh·폐기) 팀 확정 시 조정
ACCESS_TOKEN_TTL = timedelta(hours=24)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=ALGORITHM)


def decode_access_token(token: str) -> int:
    """유효하면 user_id를 반환한다. 무효·만료 토큰이면 jwt.PyJWTError."""
    payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[ALGORITHM])
    return int(payload["sub"])
