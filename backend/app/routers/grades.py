from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import GradeLevel, Mistake, User
from app.routers.deps import get_current_user
from app.schemas import GradeCreate, GradeOut, GradeUpdate

router = APIRouter(prefix="/api/grades", tags=["grades"])


@router.get("", response_model=list[GradeOut])
async def list_grades(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GradeOut]:
    result = await db.execute(select(GradeLevel).order_by(GradeLevel.sort_order, GradeLevel.level))
    rows = result.scalars().all()
    return [GradeOut.model_validate(r) for r in rows]


@router.post("", response_model=GradeOut)
async def create_grade(
    body: GradeCreate,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GradeOut:
    result = await db.execute(select(GradeLevel).where(GradeLevel.level == body.level))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该年级序号已存在")
    row = GradeLevel(
        level=body.level,
        name=body.name,
        is_builtin=False,
        sort_order=body.sort_order if body.sort_order is not None else body.level,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return GradeOut.model_validate(row)


@router.patch("/{grade_id}", response_model=GradeOut)
async def update_grade(
    grade_id: str,
    body: GradeUpdate,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GradeOut:
    row = await db.get(GradeLevel, grade_id)
    if not row:
        raise HTTPException(status_code=404, detail="年级不存在")
    if body.name is not None:
        row.name = body.name
    if body.sort_order is not None:
        row.sort_order = body.sort_order
    await db.commit()
    await db.refresh(row)
    return GradeOut.model_validate(row)


@router.delete("/{grade_id}")
async def delete_grade(
    grade_id: str,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    row = await db.get(GradeLevel, grade_id)
    if not row:
        raise HTTPException(status_code=404, detail="年级不存在")
    if row.is_builtin:
        raise HTTPException(status_code=400, detail="内置年级不可删除")
    r2 = await db.execute(select(Mistake).where(Mistake.grade_level_id == grade_id).limit(1))
    if r2.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该年级下仍有错题，无法删除")
    await db.delete(row)
    await db.commit()
    return {"status": "ok"}
