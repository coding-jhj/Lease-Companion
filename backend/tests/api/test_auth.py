"""회원 API(signup/login/me) 흐름 테스트. sqlite 임시 파일 DB 사용."""

import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test_auth.db"
os.environ["JWT_SECRET"] = "test-secret"

import pytest
from fastapi.testclient import TestClient

from app.main import app

SIGNUP = {"username": "user_a", "email": "a@test.com", "password": "password1!"}


@pytest.fixture(scope="module")
def client():
    # with 블록이 lifespan(테이블 생성)을 실행시킨다
    with TestClient(app) as c:
        yield c


def test_signup(client):
    res = client.post("/api/auth/signup", json=SIGNUP)
    assert res.status_code == 201
    assert res.json()["username"] == "user_a"
    assert res.json()["email"] == "a@test.com"


def test_signup_duplicate_username(client):
    res = client.post("/api/auth/signup", json={**SIGNUP, "email": "other@test.com"})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "username_taken"


def test_signup_duplicate_email(client):
    res = client.post("/api/auth/signup", json={**SIGNUP, "username": "user_b"})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "email_taken"


def test_signup_short_password(client):
    res = client.post("/api/auth/signup", json={**SIGNUP, "username": "user_c", "email": "c@test.com", "password": "xk29!q"})
    assert res.status_code == 422
    error = res.json()["error"]
    assert error["code"] == "validation_error"
    # 입력한 비밀번호가 응답에 되돌아오지 않아야 한다
    assert "xk29!q" not in res.text


@pytest.mark.parametrize(
    "password",
    [
        "abcdefg!",   # 숫자 없음
        "abcd1234",   # 특수문자 없음
        "1234!@#$",   # 영문 없음
    ],
)
def test_signup_password_composition(client, password):
    res = client.post("/api/auth/signup", json={**SIGNUP, "username": "user_d", "email": "d@test.com", "password": password})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


def test_signup_bad_username(client):
    res = client.post("/api/auth/signup", json={**SIGNUP, "username": "한글아이디", "email": "e@test.com"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


def test_login_wrong_password(client):
    res = client.post("/api/auth/login", json={"username": "user_a", "password": "wrong-password"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "invalid_credentials"


def test_login_unknown_username_same_error(client):
    res = client.post("/api/auth/login", json={"username": "nobody", "password": "password1!"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "invalid_credentials"


def test_login_and_me(client):
    res = client.post("/api/auth/login", json={"username": "user_a", "password": "password1!"})
    assert res.status_code == 200
    token = res.json()["access_token"]

    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["username"] == "user_a"


def test_me_without_token(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_me_with_bad_token(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert res.status_code == 401
