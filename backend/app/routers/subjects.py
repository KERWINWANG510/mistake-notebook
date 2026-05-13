from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Mistake, Subject, User
from app.routers.deps import get_current_user
from app.schemas import SubjectCreate, SubjectOut, SubjectUpdate

router = APIRouter(prefix="/api/subjects", tags=["subjects"])


@router.get("", response_model=list[SubjectOut])
async def list_subjects(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubjectOut]:
    result = await db.execute(select(Subject).order_by(Subject.sort_order, Subject.name))
    rows = result.scalars().all()
    return [SubjectOut.model_validate(r) for r in rows]


@router.post("", response_model=SubjectOut)
async def create_subject(
    body: SubjectCreate,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubjectOut:
    if body.code:
        r = await db.execute(select(Subject).where(Subject.code == body.code))
        if r.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="科目编码已存在")
    row = Subject(
        name=body.name,
        code=body.code,
        is_builtin=False,
        sort_order=999,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return SubjectOut.model_validate(row)


@router.patch("/{subject_id}", response_model=SubjectOut)
async def update_subject(
    subject_id: str,
    body: SubjectUpdate,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubjectOut:
    row = await db.get(Subject, subject_id)
    if not row:
        raise HTTPException(status_code=404, detail="科目不存在")
    if body.name is not None:
        row.name = body.name
    if body.sort_order is not None:
        row.sort_order = body.sort_order
    await db.commit()
    await db.refresh(row)
    return SubjectOut.model_validate(row)


@router.delete("/{subject_id}")
async def delete_subject(
    subject_id: str,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    row = await db.get(Subject, subject_id)
    if not row:
        raise HTTPException(status_code=404, detail="科目不存在")
    if row.is_builtin:
        raise HTTPException(status_code=400, detail="内置科目不可删除")
    r2 = await db.execute(select(Mistake).where(Mistake.subject_id == subject_id).limit(1))
    if r2.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该科目下仍有错题，无法删除")
    await db.delete(row)
    await db.commit()
    return {"status": "ok"}
