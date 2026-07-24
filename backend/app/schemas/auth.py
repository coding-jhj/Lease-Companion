import re

from pydantic import BaseModel, EmailStr, Field, field_validator


class SignupRequest(BaseModel):
    # 로그인 아이디: 영문·숫자·밑줄, 3~30자
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=16)

    @field_validator("password")
    @classmethod
    def password_composition(cls, v: str) -> str:
        """영문 대문자·소문자·숫자·특수문자를 각각 1자 이상 포함."""
        # ponytail: 16자 상한이므로 bcrypt 72바이트 초과는 구조적으로 불가능
        if not (
            re.search(r"[A-Z]", v)
            and re.search(r"[a-z]", v)
            and re.search(r"\d", v)
            and re.search(r"[^A-Za-z0-9]", v)
        ):
            raise ValueError(
                "비밀번호는 8~16자 영문 대소문자, 숫자, 특수문자를 조합해야 합니다."
            )
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
