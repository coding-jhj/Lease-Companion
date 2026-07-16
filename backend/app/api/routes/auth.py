from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core import security
from app.core.db import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", status_code=201, response_model=UserResponse)
def signup(body: SignupRequest, db: Session = Depends(get_db)) -> User:
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(
            status_code=409,
            detail={"code": "username_taken", "message": "이미 사용 중인 아이디입니다."},
        )
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(
            status_code=409,
            detail={"code": "email_taken", "message": "이미 가입된 이메일입니다."},
        )
    user = User(
        username=body.username,
        email=body.email,
        password_hash=security.hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == body.username))
    # 계정 존재 여부가 드러나지 않게 두 실패를 같은 응답으로 처리
    if user is None or not security.verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_credentials", "message": "아이디 또는 비밀번호가 올바르지 않습니다."},
        )
    return TokenResponse(access_token=security.create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user
