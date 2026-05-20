from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.avatars import (
    MAX_AVATAR_BYTES,
    avatar_relative_path,
    avatar_storage_path,
    delete_stored_avatar,
    media_type_for_path,
    normalize_avatar_ext,
    resolve_avatar_file,
)
from app.database import get_db
from app.education import EDUCATION_STAGES
from app.models import Mistake, User
from app.routers.deps import get_current_user, require_admin
from app.schemas import (
    EducationStageOut,
    LoginBody,
    TokenOut,
    UserCreateBody,
    UserOut,
    UserProfileUpdateBody,
    UserUpdateBody,
)
from app.services.jwt_tokens import create_access_token
from app.services.password import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut.from_user(user)


async def _get_user_or_404(user_id: str, db: AsyncSession) -> User:
    row = await db.get(User, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    return row


def _validate_gender(gender: str | None) -> None:
    if gender is not None and gender not in ("male", "female"):
        raise HTTPException(status_code=400, detail="性别仅支持 male 或 female")


async def _save_user_avatar(row: User, raw: bytes, filename: str | None, db: AsyncSession) -> UserOut:
    if len(raw) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail="头像文件过大（最大 5MB）")
    ext = normalize_avatar_ext(filename)
    dest = avatar_storage_path(row.id, ext)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if row.avatar_path:
        delete_stored_avatar(row.avatar_path)
    dest.write_bytes(raw)
    row.avatar_path = avatar_relative_path(row.id, ext)
    await db.commit()
    await db.refresh(row)
    return _user_out(row)


@router.get("/education-stages", response_model=list[EducationStageOut])
async def list_education_stages() -> list[EducationStageOut]:
    """内置教育阶段，供注册/建用户表单使用。"""
    return [EducationStageOut(code=c, name=n) for c, n in EDUCATION_STAGES]


@router.post("/login", response_model=TokenOut)
async def login(body: LoginBody, db: AsyncSession = Depends(get_db)) -> TokenOut:
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    token = create_access_token(user_id=user.id, username=user.username, is_admin=user.is_admin)
    return TokenOut(
        access_token=token,
        token_type="bearer",
        user=_user_out(user),
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UserProfileUpdateBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    row = user
    if body.username is not None:
        username = body.username.strip()
        if username != row.username:
            exists = await db.execute(select(User).where(User.username == username))
            if exists.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="用户名已存在")
            row.username = username
    if body.full_name is not None:
        row.full_name = body.full_name.strip()
    if body.education_stage is not None:
        row.education_stage = body.education_stage
    if body.enrollment_year is not None:
        row.enrollment_year = body.enrollment_year
    patch_data = body.model_dump(exclude_unset=True)
    if "gender" in patch_data:
        g = patch_data["gender"]
        if g is not None:
            _validate_gender(g)
        row.gender = g
    if body.clear_avatar:
        delete_stored_avatar(row.avatar_path)
        row.avatar_path = None
    if body.password is not None:
        row.password_hash = hash_password(body.password)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="用户名已存在") from None
    await db.refresh(row)
    return _user_out(row)


@router.get("/users/{user_id}/avatar")
async def get_user_avatar(
    user_id: str,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    row = await _get_user_or_404(user_id, db)
    path = resolve_avatar_file(row)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="头像不存在")
    return FileResponse(path, media_type=media_type_for_path(path))


@router.post("/me/avatar", response_model=UserOut)
async def upload_my_avatar(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    image: UploadFile = File(...),
) -> UserOut:
    raw = await image.read()
    return await _save_user_avatar(user, raw, image.filename, db)


@router.delete("/me/avatar", response_model=UserOut)
async def delete_my_avatar(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    delete_stored_avatar(user.avatar_path)
    user.avatar_path = None
    await db.commit()
    await db.refresh(user)
    return _user_out(user)


@router.post("/users/{user_id}/avatar", response_model=UserOut)
async def upload_user_avatar(
    user_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    image: UploadFile = File(...),
) -> UserOut:
    row = await _get_user_or_404(user_id, db)
    raw = await image.read()
    return await _save_user_avatar(row, raw, image.filename, db)


@router.get("/users", response_model=list[UserOut])
async def list_users(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> list[UserOut]:
    result = await db.execute(select(User).order_by(User.created_at.asc()))
    rows = result.scalars().all()
    return [_user_out(u) for u in rows]


@router.post("/users", response_model=UserOut)
async def create_user(
    body: UserCreateBody,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    exists = await db.execute(select(User).where(User.username == body.username.strip()))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if body.gender is not None:
        _validate_gender(body.gender)
    row = User(
        username=body.username.strip(),
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
        education_stage=body.education_stage,
        enrollment_year=body.enrollment_year,
        gender=body.gender,
        is_admin=False,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="用户名已存在") from None
    await db.refresh(row)
    return _user_out(row)


async def _admin_count(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(User).where(User.is_admin.is_(True)))
    return int(result.scalar_one())


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    body: UserUpdateBody,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    row = await _get_user_or_404(user_id, db)

    if body.username is not None:
        username = body.username.strip()
        if username != row.username:
            exists = await db.execute(select(User).where(User.username == username))
            if exists.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="用户名已存在")
            row.username = username

    if body.full_name is not None:
        row.full_name = body.full_name.strip()
    if body.education_stage is not None:
        row.education_stage = body.education_stage
    if body.enrollment_year is not None:
        row.enrollment_year = body.enrollment_year
    patch_data = body.model_dump(exclude_unset=True)
    if "gender" in patch_data:
        g = patch_data["gender"]
        if g is not None:
            _validate_gender(g)
        row.gender = g
    if body.clear_avatar:
        delete_stored_avatar(row.avatar_path)
        row.avatar_path = None
    if body.password is not None:
        row.password_hash = hash_password(body.password)

    if body.is_admin is not None and body.is_admin != row.is_admin:
        if row.is_admin and not body.is_admin:
            if row.id == admin.id:
                raise HTTPException(status_code=400, detail="不能取消自己的管理员权限")
            if await _admin_count(db) <= 1:
                raise HTTPException(status_code=400, detail="至少保留一名管理员")
        row.is_admin = body.is_admin

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="用户名已存在") from None
    await db.refresh(row)
    return _user_out(row)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")

    row = await _get_user_or_404(user_id, db)

    if row.is_admin and await _admin_count(db) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一名管理员")

    delete_stored_avatar(row.avatar_path)
    await db.execute(delete(Mistake).where(Mistake.user_id == user_id))
    await db.delete(row)
    await db.commit()
    return {"status": "ok"}
