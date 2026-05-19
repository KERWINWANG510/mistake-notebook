import json
import uuid
from pathlib import Path

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.database import get_db
from app.models import GradeLevel, GradeSubject, Mistake, Subject, User
from app.error_reasons import ERROR_REASON_OPTIONS, error_reason_label, parse_error_reason
from app.knowledge_tags import normalize_knowledge_tags as _normalize_tags
from app.routers.deps import get_current_user
from app.schemas import ErrorReasonOptionOut, KnowledgeTagCount, MistakeOut, MistakeUpdate, SubjectMistakeSummary

router = APIRouter(prefix="/api/mistakes", tags=["mistakes"])


def _mistake_out(m: Mistake) -> MistakeOut:
    return MistakeOut(
        id=m.id,
        subject_id=m.subject_id,
        grade_level_id=m.grade_level_id,
        stem=m.stem,
        analysis=m.analysis,
        answer=m.answer,
        image_path=m.image_path,
        is_mastered=m.is_mastered,
        knowledge_tags=list(m.knowledge_tags or []),
        error_reason=m.error_reason,
        error_reason_label=error_reason_label(m.error_reason),
        created_at=m.created_at,
        updated_at=m.updated_at,
        subject_name=m.subject.name if m.subject else None,
        grade_name=m.grade.name if m.grade else None,
    )


def _require_owner(m: Mistake | None, user: User) -> Mistake:
    if not m:
        raise HTTPException(status_code=404, detail="错题不存在")
    if m.user_id != user.id:
        raise HTTPException(status_code=404, detail="错题不存在")
    return m


@router.get("/error-reasons", response_model=list[ErrorReasonOptionOut])
async def list_error_reasons() -> list[ErrorReasonOptionOut]:
    """错因下拉选项（稳定 code + 中文标签）。"""
    return [ErrorReasonOptionOut(**o) for o in ERROR_REASON_OPTIONS]


@router.get("", response_model=list[MistakeOut])
async def list_mistakes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    subject_id: str | None = None,
    grade_level_id: str | None = None,
    mastery: Literal["mastered", "unmastered", "all"] = "unmastered",
    knowledge_tag: str | None = None,
) -> list[MistakeOut]:
    q = (
        select(Mistake)
        .options(joinedload(Mistake.subject), joinedload(Mistake.grade))
        .where(Mistake.user_id == user.id)
        .order_by(Mistake.created_at.desc())
    )
    if subject_id:
        q = q.where(Mistake.subject_id == subject_id)
    if grade_level_id:
        q = q.where(Mistake.grade_level_id == grade_level_id)
    if mastery == "mastered":
        q = q.where(Mistake.is_mastered.is_(True))
    elif mastery == "unmastered":
        q = q.where(Mistake.is_mastered.is_(False))
    if knowledge_tag:
        tag = knowledge_tag.strip()
        if tag:
            q = q.where(
                text(
                    "EXISTS (SELECT 1 FROM json_each(mistakes.knowledge_tags) "
                    "WHERE json_each.value = :ktag)"
                ).bindparams(ktag=tag)
            )
    result = await db.execute(q)
    rows = result.unique().scalars().all()
    return [_mistake_out(m) for m in rows]


def _tag_counts_from_rows(
    tag_rows: list[tuple[str, list | None]],
) -> dict[str, dict[str, int]]:
    tags_by_subject: dict[str, dict[str, int]] = {}
    for subject_id, ktags in tag_rows:
        for t in ktags or []:
            if not t:
                continue
            bucket = tags_by_subject.setdefault(subject_id, {})
            bucket[t] = bucket.get(t, 0) + 1
    return tags_by_subject


def _summaries_from_tag_map(
    tag_map: dict[str, dict[str, int]],
    counts: dict[str, int],
    *,
    subject_meta: dict[str, tuple[str, str | None]],
) -> list[SubjectMistakeSummary]:
    def tag_counts_for(subject_id: str) -> list[KnowledgeTagCount]:
        items = tag_map.get(subject_id, {})
        return [
            KnowledgeTagCount(tag=name, count=cnt)
            for name, cnt in sorted(items.items(), key=lambda x: (-x[1], x[0]))
        ]

    rows = [
        SubjectMistakeSummary(
            subject_id=sid,
            subject_name=subject_meta[sid][0],
            subject_code=subject_meta[sid][1],
            mistake_count=int(counts.get(sid, 0)),
            knowledge_tags=tag_counts_for(sid),
        )
        for sid in counts
        if sid in subject_meta and counts.get(sid, 0) > 0
    ]
    rows.sort(key=lambda r: (-r.mistake_count, r.subject_name))
    return rows


async def _subject_mistake_summary_all_grades(
    user: User,
    db: AsyncSession,
) -> list[SubjectMistakeSummary]:
    """当前用户各科目未掌握错题汇总（不限年级）。"""
    counts_q = (
        select(
            Mistake.subject_id,
            func.count(Mistake.id).label("mistake_count"),
        )
        .where(
            Mistake.user_id == user.id,
            Mistake.is_mastered.is_(False),
        )
        .group_by(Mistake.subject_id)
    )
    count_rows = (await db.execute(counts_q)).all()
    counts = {row.subject_id: row.mistake_count for row in count_rows}
    if not counts:
        return []

    subject_ids = list(counts.keys())
    subjects = (
        await db.execute(select(Subject.id, Subject.name, Subject.code).where(Subject.id.in_(subject_ids)))
    ).all()
    subject_meta = {row.id: (row.name, row.code) for row in subjects}

    tag_rows = (
        await db.execute(
            select(Mistake.subject_id, Mistake.knowledge_tags).where(
                Mistake.user_id == user.id,
                Mistake.is_mastered.is_(False),
                Mistake.subject_id.in_(subject_ids),
            )
        )
    ).all()
    tag_map = _tag_counts_from_rows(tag_rows)
    return _summaries_from_tag_map(tag_map, counts, subject_meta=subject_meta)


@router.get("/summary/by-subject", response_model=list[SubjectMistakeSummary])
async def subject_mistake_summary(
    grade_level_id: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubjectMistakeSummary]:
    if grade_level_id is None or not str(grade_level_id).strip():
        return await _subject_mistake_summary_all_grades(user, db)

    if not await db.get(GradeLevel, grade_level_id):
        raise HTTPException(status_code=400, detail="年级不存在")

    catalog = (
        await db.execute(
            select(Subject.id, Subject.name, Subject.code, GradeSubject.sort_order)
            .join(GradeSubject, GradeSubject.subject_id == Subject.id)
            .where(GradeSubject.grade_level_id == grade_level_id)
            .order_by(GradeSubject.sort_order, Subject.name)
        )
    ).all()

    counts_q = (
        select(
            Mistake.subject_id,
            func.count(Mistake.id).label("mistake_count"),
        )
        .where(
            Mistake.user_id == user.id,
            Mistake.grade_level_id == grade_level_id,
            Mistake.is_mastered.is_(False),
        )
        .group_by(Mistake.subject_id)
    )
    counts = {row.subject_id: row.mistake_count for row in (await db.execute(counts_q)).all()}

    tag_rows = (
        await db.execute(
            select(Mistake.subject_id, Mistake.knowledge_tags).where(
                Mistake.user_id == user.id,
                Mistake.grade_level_id == grade_level_id,
                Mistake.is_mastered.is_(False),
            )
        )
    ).all()
    tags_by_subject = _tag_counts_from_rows(tag_rows)

    def tag_counts_for(subject_id: str) -> list[KnowledgeTagCount]:
        items = tags_by_subject.get(subject_id, {})
        return [
            KnowledgeTagCount(tag=name, count=cnt)
            for name, cnt in sorted(items.items(), key=lambda x: (-x[1], x[0]))
        ]

    if catalog:
        rows = [
            SubjectMistakeSummary(
                subject_id=row.id,
                subject_name=row.name,
                subject_code=row.code,
                mistake_count=int(counts.get(row.id, 0)),
                knowledge_tags=tag_counts_for(row.id),
            )
            for row in catalog
        ]
        rows = [r for r in rows if r.mistake_count > 0]
        rows.sort(key=lambda r: (-r.mistake_count, r.subject_name))
        return rows

    q = (
        select(
            Mistake.subject_id,
            Subject.name,
            Subject.code,
            func.count(Mistake.id).label("mistake_count"),
        )
        .join(Subject, Mistake.subject_id == Subject.id)
        .where(
            Mistake.user_id == user.id,
            Mistake.grade_level_id == grade_level_id,
            Mistake.is_mastered.is_(False),
        )
        .group_by(Mistake.subject_id, Subject.name, Subject.code)
        .order_by(func.count(Mistake.id).desc(), Subject.name.asc())
    )
    result = await db.execute(q)
    return [
        SubjectMistakeSummary(
            subject_id=row.subject_id,
            subject_name=row.name,
            subject_code=row.code,
            mistake_count=row.mistake_count,
            knowledge_tags=tag_counts_for(row.subject_id),
        )
        for row in result.all()
    ]


@router.get("/{mistake_id}/image")
async def get_mistake_image(
    mistake_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    m = _require_owner(await db.get(Mistake, mistake_id), user)
    if not m.image_path:
        raise HTTPException(status_code=404, detail="该错题没有图片")
    path = get_settings().upload_dir / m.image_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片文件不存在")
    return FileResponse(path)


@router.post("/{mistake_id}/image", response_model=MistakeOut)
async def replace_mistake_image(
    mistake_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    image: UploadFile = File(...),
) -> MistakeOut:
    m = _require_owner(await db.get(Mistake, mistake_id), user)
    raw = await image.read()
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片过大")
    ext = Path(image.filename or "").suffix.lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    fname = f"{mistake_id}{ext}"
    dest = get_settings().upload_dir / fname
    dest.parent.mkdir(parents=True, exist_ok=True)
    if m.image_path and m.image_path != fname:
        old = get_settings().upload_dir / m.image_path
        if old.is_file():
            old.unlink(missing_ok=True)
    dest.write_bytes(raw)
    m.image_path = fname
    await db.commit()
    q = (
        select(Mistake)
        .options(joinedload(Mistake.subject), joinedload(Mistake.grade))
        .where(Mistake.id == mistake_id)
    )
    result = await db.execute(q)
    m2 = result.unique().scalar_one()
    return _mistake_out(m2)


@router.get("/{mistake_id}", response_model=MistakeOut)
async def get_mistake(mistake_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> MistakeOut:
    q = (
        select(Mistake)
        .options(joinedload(Mistake.subject), joinedload(Mistake.grade))
        .where(Mistake.id == mistake_id)
    )
    result = await db.execute(q)
    m = result.unique().scalar_one_or_none()
    return _mistake_out(_require_owner(m, user))


@router.post("", response_model=MistakeOut)
async def create_mistake(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    subject_id: str = Form(...),
    grade_level_id: str = Form(...),
    stem: str = Form(...),
    analysis: str = Form(""),
    answer: str = Form(""),
    knowledge_tags: str = Form("[]"),
    error_reason: str = Form(...),
    image: UploadFile | None = File(None),
) -> MistakeOut:
    try:
        reason_code = parse_error_reason(error_reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not await db.get(Subject, subject_id):
        raise HTTPException(status_code=400, detail="科目不存在")
    if not await db.get(GradeLevel, grade_level_id):
        raise HTTPException(status_code=400, detail="年级不存在")

    try:
        raw_tags = json.loads(knowledge_tags) if knowledge_tags else []
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="知识点标签格式不正确") from e
    if not isinstance(raw_tags, list):
        raise HTTPException(status_code=400, detail="知识点标签须为数组")
    tags = _normalize_tags([str(t) for t in raw_tags])

    mid = str(uuid.uuid4())
    image_rel: str | None = None
    if image and image.filename:
        raw = await image.read()
        if len(raw) > 15 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="图片过大")
        ext = Path(image.filename).suffix.lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            ext = ".jpg"
        fname = f"{mid}{ext}"
        dest = get_settings().upload_dir / fname
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        image_rel = fname

    row = Mistake(
        id=mid,
        user_id=user.id,
        subject_id=subject_id,
        grade_level_id=grade_level_id,
        stem=stem,
        analysis=analysis or "",
        answer=answer or "",
        image_path=image_rel,
        knowledge_tags=tags,
        error_reason=reason_code,
    )
    db.add(row)
    await db.commit()
    q = (
        select(Mistake)
        .options(joinedload(Mistake.subject), joinedload(Mistake.grade))
        .where(Mistake.id == mid)
    )
    result = await db.execute(q)
    m = result.unique().scalar_one()
    return _mistake_out(m)


@router.patch("/{mistake_id}", response_model=MistakeOut)
async def update_mistake(
    mistake_id: str,
    body: MistakeUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MistakeOut:
    m = _require_owner(await db.get(Mistake, mistake_id), user)
    if body.subject_id is not None:
        if not await db.get(Subject, body.subject_id):
            raise HTTPException(status_code=400, detail="科目不存在")
        m.subject_id = body.subject_id
    if body.grade_level_id is not None:
        if not await db.get(GradeLevel, body.grade_level_id):
            raise HTTPException(status_code=400, detail="年级不存在")
        m.grade_level_id = body.grade_level_id
    if body.stem is not None:
        m.stem = body.stem
    if body.analysis is not None:
        m.analysis = body.analysis
    if body.answer is not None:
        m.answer = body.answer
    if body.is_mastered is not None:
        m.is_mastered = body.is_mastered
    if body.knowledge_tags is not None:
        m.knowledge_tags = _normalize_tags(body.knowledge_tags)
    if body.error_reason is not None:
        try:
            m.error_reason = parse_error_reason(body.error_reason)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    q = (
        select(Mistake)
        .options(joinedload(Mistake.subject), joinedload(Mistake.grade))
        .where(Mistake.id == mistake_id)
    )
    result = await db.execute(q)
    m2 = result.unique().scalar_one()
    return _mistake_out(m2)


@router.delete("/{mistake_id}")
async def delete_mistake(mistake_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    m = _require_owner(await db.get(Mistake, mistake_id), user)
    if m.image_path:
        p = get_settings().upload_dir / m.image_path
        if p.is_file():
            p.unlink(missing_ok=True)
    await db.delete(m)
    await db.commit()
    return {"status": "ok"}
