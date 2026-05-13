"""API Key 等敏感字段的对称加解密（依赖 APP_SECRET）。"""

import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import get_settings


def _fernet() -> Fernet:
    secret = get_settings().app_secret.encode("utf-8")
    key = hashlib.sha256(secret).digest()
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)


def encrypt_secret(plain: str | None) -> bytes | None:
    if plain is None or plain == "":
        return None
    return _fernet().encrypt(plain.encode("utf-8"))


def decrypt_secret(blob: bytes | None) -> str | None:
    if blob is None:
        return None
    return _fernet().decrypt(blob).decode("utf-8")
