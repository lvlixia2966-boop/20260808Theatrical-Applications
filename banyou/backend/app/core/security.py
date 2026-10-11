"""安全工具：密码哈希、JWT 签发与校验（与主项目同款实现）。"""
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import settings


def pwd_version(password_hash: str) -> str:
    """口令版本指纹：入 token 的 pwdv 声明，口令一变旧 token 即失效（同主项目）。"""
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:16]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, extra: dict | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_payload(token: str) -> dict | None:
    """解析 JWT 返回完整 payload；无效/过期返回 None。"""
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def decode_token(token: str) -> str | None:
    """解析 JWT，返回 subject；无效/过期返回 None。"""
    payload = decode_payload(token)
    return payload.get("sub") if payload else None
