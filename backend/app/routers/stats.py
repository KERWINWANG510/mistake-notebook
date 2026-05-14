"""错题统计聚合。"""

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import GradeLevel, Mistake, Subject, User
from app.routers.deps import get_current_user
from app.schemas import MistakeStatsGradeRow, MistakeStatsOverview, MistakeStatsSubjectRow, MistakeStatsTagRow

router = APIRouter(prefix="/api/stats", tags=["stats"])


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

    tag_sql = text(
        """
        SELECT TRIM(je.value) AS tag, COUNT(*) AS cnt
        FROM mistakes m, json_each(COALESCE(m.knowledge_tags, '[]')) AS je
        WHERE m.user_id = :uid AND LENGTH(TRIM(je.value)) > 0
        GROUP BY TRIM(je.value)
        ORDER BY cnt DESC, tag ASC
        LIMIT 50
        """
    )
    tag_rows = (await db.execute(tag_sql, {"uid": user.id})).all()
    by_tag = [MistakeStatsTagRow(tag=row.tag, mistake_count=int(row.cnt)) for row in tag_rows]

    return MistakeStatsOverview(
        total_mistake_count=total_mistake_count,
        mastered_count=mastered_count,
        mastery_rate_percent=mastery_rate_percent,
        by_grade=by_grade,
        by_subject=by_subject,
        by_tag=by_tag,
    )
