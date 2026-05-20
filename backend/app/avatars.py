"""用户头像：上传校验、存储路径与内置默认图。"""

from pathlib import Path

from fastapi import HTTPException

from app.config import get_settings
from app.models import User

AVATAR_SUBDIR = "avatars"
ALLOWED_AVATAR_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})
MAX_AVATAR_BYTES = 5 * 1024 * 1024

_BUILTIN_DIR = Path(__file__).resolve().parent / "assets" / "avatars"
_BUILTIN_MALE = _BUILTIN_DIR / "default_male.svg"
_BUILTIN_FEMALE = _BUILTIN_DIR / "default_female.svg"

_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}


def normalize_avatar_ext(filename: str | None) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 JPG、PNG、WebP、GIF 格式的头像")
    return ext


def media_type_for_path(path: Path) -> str:
    return _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


def avatar_storage_path(user_id: str, ext: str) -> Path:
    return get_settings().upload_dir / AVATAR_SUBDIR / f"{user_id}{ext}"


def avatar_relative_path(user_id: str, ext: str) -> str:
    return f"{AVATAR_SUBDIR}/{user_id}{ext}"


def resolve_custom_avatar_path(avatar_path: str | None) -> Path | None:
    if not avatar_path:
        return None
    path = get_settings().upload_dir / avatar_path
    return path if path.is_file() else None


def builtin_avatar_path(gender: str | None) -> Path:
    if gender == "female":
        return _BUILTIN_FEMALE
    return _BUILTIN_MALE


def resolve_avatar_file(user: User) -> Path:
    custom = resolve_custom_avatar_path(user.avatar_path)
    if custom:
        return custom
    return builtin_avatar_path(user.gender)


def delete_stored_avatar(avatar_path: str | None) -> None:
    path = resolve_custom_avatar_path(avatar_path)
    if path:
        path.unlink(missing_ok=True)
