from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import GradeLevel, User
from app.routers.deps import get_current_user
from app.schemas import GradeOut

router = APIRouter(prefix="/api/grades", tags=["grades"])

_GRADE_READONLY_MSG = "年级为系统内置数据，不支持新增、修改或删除"


@router.get("", response_model=list[GradeOut])
async def list_grades(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GradeOut]:
    result = await db.execute(select(GradeLevel).order_by(GradeLevel.sort_order, GradeLevel.level))
    rows = result.scalars().all()
    return [GradeOut.model_validate(r) for r in rows]


@router.post("", response_model=GradeOut)
async def create_grade(_: User = Depends(get_current_user)) -> GradeOut:
    raise HTTPException(status_code=403, detail=_GRADE_READONLY_MSG)


@router.patch("/{grade_id}", response_model=GradeOut)
async def update_grade(grade_id: str, _: User = Depends(get_current_user)) -> GradeOut:
    raise HTTPException(status_code=403, detail=_GRADE_READONLY_MSG)


@router.delete("/{grade_id}")
async def delete_grade(grade_id: str, _: User = Depends(get_current_user)) -> dict[str, str]:
    raise HTTPException(status_code=403, detail=_GRADE_READONLY_MSG)
