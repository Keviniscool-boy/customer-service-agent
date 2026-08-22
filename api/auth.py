from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from agent.database import (
    create_user,
    get_user_by_username,
    init_db,
    update_user_password,
)
from config.settings import settings


password_hash = PasswordHash.recommended()
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
MAX_USERNAME_LENGTH = 64
MAX_PASSWORD_LENGTH = 128


def register_user(username: str, password: str) -> dict:
    username = username.strip()
    if len(username) < 3:
        raise ValueError("用户名至少需要 3 个字符")
    if len(username) > MAX_USERNAME_LENGTH:
        raise ValueError("用户名不能超过 64 个字符")
    if len(password) < 6:
        raise ValueError("密码至少需要 6 个字符")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError("密码不能超过 128 个字符")

    init_db()
    if get_user_by_username(username):
        raise ValueError("用户名已存在")

    user_id = create_user(username, password_hash.hash(password))
    return {"id": user_id, "username": username, "role": "user"}


def authenticate_user(username: str, password: str) -> dict | None:
    if len(username.strip()) > MAX_USERNAME_LENGTH:
        return None
    if len(password) > MAX_PASSWORD_LENGTH:
        return None
    init_db()
    user = get_user_by_username(username.strip())
    if not user or not password_hash.verify(password, user["password_hash"]):
        return None
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user.get("role", "user"),
    }


def reset_user_password(username: str, password: str) -> None:
    if len(password) < 6:
        raise ValueError("密码至少需要 6 个字符")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError("密码不能超过 128 个字符")

    init_db()
    if not get_user_by_username(username.strip()):
        raise ValueError("用户不存在")

    update_user_password(username.strip(), password_hash.hash(password))


def create_access_token(user: dict) -> str:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET 未配置")

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "role": user.get("role", "user"),
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET 未配置")
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[JWT_ALGORITHM],
    )
