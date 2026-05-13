from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.education import EDUCATION_STAGES
from app.models import User
from app.routers.deps import get_current_user, require_admin
from app.schemas import EducationStageOut, LoginBody, TokenOut, UserCreateBody, UserOut
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
