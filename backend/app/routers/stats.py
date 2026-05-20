"""错题统计聚合。"""

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import GradeLevel, Mistake, Subject, User
from app.routers.deps import get_current_user
from app.error_reasons import ERROR_REASON_OPTIONS, canonical_error_reason
from app.mistake_sources import MISTAKE_SOURCE_OPTIONS
from app.schemas import (
    MistakeStatsErrorReasonHeatmap,
    MistakeStatsGradeRow,
    MistakeStatsOverview,
    MistakeStatsSourceRow,
    MistakeStatsSubjectRow,
    MistakeStatsTagRow,
)

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _tag_stats_rows(
    tag_rows: list,
) -> list[MistakeStatsTagRow]:
    return [MistakeStatsTagRow(tag=row.tag, mistake_count=int(row.cnt)) for row in tag_rows]


async def _query_source_stats(db: AsyncSession, user_id: str) -> list[MistakeStatsSourceRow]:
    """按错题来源汇总（固定三项，无数据为 0）。"""
    q = (
        select(Mistake.mistake_source, func.count(Mistake.id).label("cnt"))
        .where(
            Mistake.user_id == user_id,
            Mistake.mistake_source.is_not(None),
            Mistake.mistake_source != "",
        )
        .group_by(Mistake.mistake_source)
    )
    counts = {row.mistake_source: int(row.cnt) for row in (await db.execute(q)).all()}
    return [
        MistakeStatsSourceRow(
            source_code=o["code"],
            source_label=o["label"],
            mistake_count=counts.get(o["code"], 0),
        )
        for o in MISTAKE_SOURCE_OPTIONS
    ]


async def _query_tag_stats(
    db: AsyncSession,
    user_id: str,
    *,
    subject_id: str | None = None,
    grade_level_id: str | None = None,
) -> list[MistakeStatsTagRow]:
    """按用户汇总知识点标签；可选科目、年级筛选。"""
    conditions = ["m.user_id = :uid", "LENGTH(TRIM(je.value)) > 0"]
    params: dict[str, str] = {"uid": user_id}
    if subject_id:
        conditions.append("m.subject_id = :subject_id")
        params["subject_id"] = subject_id
    if grade_level_id:
        conditions.append("m.grade_level_id = :grade_level_id")
        params["grade_level_id"] = grade_level_id
    where = " AND ".join(conditions)
    tag_sql = text(
        f"""
        SELECT TRIM(je.value) AS tag, COUNT(*) AS cnt
        FROM mistakes m, json_each(COALESCE(m.knowledge_tags, '[]')) AS je
        WHERE {where}
        GROUP BY TRIM(je.value)
        ORDER BY cnt DESC, tag ASC
        LIMIT 50
        """
    )
    tag_rows = (await db.execute(tag_sql, params)).all()
    return _tag_stats_rows(tag_rows)


@router.get("/mistakes/error-reason-heatmap", response_model=MistakeStatsErrorReasonHeatmap)
async def mistake_stats_error_reason_heatmap(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MistakeStatsErrorReasonHeatmap:
    """错因 × 科目热力图：仅统计已标注错因的错题。"""
    totals_stmt = select(func.count(Mistake.id)).where(Mistake.user_id == user.id)
    total_mistake_count = int((await db.execute(totals_stmt)).scalar_one() or 0)

    q = (
        select(
            Mistake.error_reason,
            Mistake.subject_id,
            Subject.name,
            func.count(Mistake.id).label("cnt"),
        )
        .join(Subject, Mistake.subject_id == Subject.id)
        .where(
            Mistake.user_id == user.id,
            Mistake.error_reason.is_not(None),
            Mistake.error_reason != "",
        )
        .group_by(Mistake.error_reason, Mistake.subject_id, Subject.name)
    )
    rows = (await db.execute(q)).all()

    reason_codes = [o["code"] for o in ERROR_REASON_OPTIONS]
    reason_labels = [o["label"] for o in ERROR_REASON_OPTIONS]
    reason_index = {c: i for i, c in enumerate(reason_codes)}

    subject_order: list[tuple[str, str]] = []
    subject_seen: set[str] = set()
    for row in sorted(rows, key=lambda r: (-int(r.cnt), r.name or "")):
        if row.subject_id not in subject_seen:
            subject_seen.add(row.subject_id)
            subject_order.append((row.subject_id, row.name or ""))

    cells: list[list[int]] = []
    annotated = 0
    for row in rows:
        reason_code = canonical_error_reason(row.error_reason or "") or ""
        ri = reason_index.get(reason_code)
        if ri is None:
            continue
        try:
            si = next(i for i, (sid, _) in enumerate(subject_order) if sid == row.subject_id)
        except StopIteration:
            continue
        cnt = int(row.cnt)
        annotated += cnt
        cells.append([si, ri, cnt])

    return MistakeStatsErrorReasonHeatmap(
        reason_codes=reason_codes,
        reason_labels=reason_labels,
        subject_ids=[s[0] for s in subject_order],
        subject_names=[s[1] for s in subject_order],
        cells=cells,
        annotated_mistake_count=annotated,
        total_mistake_count=total_mistake_count,
    )


@router.get("/mistakes/tags", response_model=list[MistakeStatsTagRow])
async def mistake_stats_tags(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    subject_id: str | None = None,
    grade_level_id: str | None = None,
) -> list[MistakeStatsTagRow]:
    """按知识点标签汇总错题数；可按科目、年级筛选。"""
    return await _query_tag_stats(
        db,
        user.id,
        subject_id=subject_id,
        grade_level_id=grade_level_id,
    )


@router.get("/mistakes", response_model=MistakeStatsOverview)
async def mistake_stats_overview(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MistakeStatsOverview:
    """按当前登录用户汇总错题数量：年级、科目、知识点标签（含已掌握与未掌握）。"""
    totals_stmt = select(
        func.count(Mistake.id).label("total"),
        func.coalesce(
            func.sum(case((Mistake.is_mastered.is_(True), 1), else_=0)),
            0,
        ).label("mastered"),
    ).where(Mistake.user_id == user.id)
    totals_row = (await db.execute(totals_stmt)).one()
    total_mistake_count = int(totals_row.total or 0)
    mastered_count = int(totals_row.mastered or 0)
    mastery_rate_percent = (
        round(100.0 * mastered_count / total_mistake_count, 1) if total_mistake_count else 0.0
    )

    grade_q = (
        select(
            GradeLevel.id,
            GradeLevel.name,
            GradeLevel.level,
            func.count(Mistake.id).label("cnt"),
        )
        .join(Mistake, Mistake.grade_level_id == GradeLevel.id)
        .where(Mistake.user_id == user.id)
        .group_by(GradeLevel.id, GradeLevel.name, GradeLevel.level, GradeLevel.sort_order)
        .order_by(GradeLevel.sort_order.asc(), GradeLevel.level.asc())
    )
    grade_rows = (await db.execute(grade_q)).all()
    by_grade = [
        MistakeStatsGradeRow(
            grade_level_id=row.id,
            grade_name=row.name,
            level=row.level,
            mistake_count=int(row.cnt),
        )
        for row in grade_rows
    ]

    subj_q = (
        select(
            Subject.id,
            Subject.name,
            func.count(Mistake.id).label("cnt"),
        )
        .join(Mistake, Mistake.subject_id == Subject.id)
        .where(Mistake.user_id == user.id)
        .group_by(Subject.id, Subject.name)
        .order_by(func.count(Mistake.id).desc(), Subject.name.asc())
    )
    subj_rows = (await db.execute(subj_q)).all()
    by_subject = [
        MistakeStatsSubjectRow(subject_id=row.id, subject_name=row.name, mistake_count=int(row.cnt))
        for row in subj_rows
    ]

    by_source = await _query_source_stats(db, user.id)
    tag_rows = await _query_tag_stats(db, user.id)
    by_tag = tag_rows

    return MistakeStatsOverview(
        total_mistake_count=total_mistake_count,
        mastered_count=mastered_count,
        mastery_rate_percent=mastery_rate_percent,
        by_grade=by_grade,
        by_subject=by_subject,
        by_source=by_source,
        by_tag=by_tag,
    )
