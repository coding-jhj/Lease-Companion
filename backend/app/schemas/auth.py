import re

from pydantic import BaseModel, EmailStr, Field, field_validator


class SignupRequest(BaseModel):
    # 로그인 아이디: 영문·숫자·밑줄, 3~30자
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_]+$")
    email: EmailStr
    # max 72: bcrypt가 72바이트까지만 해시함
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def password_composition(cls, v: str) -> str:
        """영문·숫자·특수문자를 각각 1자 이상 포함 (팀 확정 규칙)."""
        if not (
            re.search(r"[A-Za-z]", v)
            and re.search(r"\d", v)
            and re.search(r"[^A-Za-z0-9]", v)
        ):
            raise ValueError("비밀번호는 영문, 숫자, 특수문자를 모두 포함해야 합니다.")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr

    model_config = {"from_attributes": True}
