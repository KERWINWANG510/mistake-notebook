from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


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
    if body.password is not None:
        row.password_hash = hash_password(body.password)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="用户名已存在") from None
    await db.refresh(row)
    return UserOut.model_validate(row)


@router.get("/users", response_model=list[UserOut])
async def list_users(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> list[UserOut]:
    result = await db.execute(select(User).order_by(User.created_at.asc()))
    rows = result.scalars().all()
    return [UserOut.model_validate(u) for u in rows]


@router.post("/users", response_model=UserOut)
async def create_user(
    body: UserCreateBody,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    exists = await db.execute(select(User).where(User.username == body.username.strip()))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    row = User(
        username=body.username.strip(),
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
        education_stage=body.education_stage,
        enrollment_year=body.enrollment_year,
        is_admin=False,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="用户名已存在") from None
    await db.refresh(row)
    return UserOut.model_validate(row)


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
    row = await db.get(User, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")

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
    return UserOut.model_validate(row)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")

    row = await db.get(User, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")

    if row.is_admin and await _admin_count(db) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一名管理员")

    await db.execute(delete(Mistake).where(Mistake.user_id == user_id))
    await db.delete(row)
    await db.commit()
    return {"status": "ok"}
