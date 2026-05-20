"""复习计划数据访问辅助。"""

from datetime import date, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import (
    GradeLevel,
    Mistake,
    MistakeReview,
    ReviewSession,
    ReviewSessionItem,
    Subject,
    User,
    UserReviewSettings,
)
from app.review_schedule import end_of_utc_day, initial_next_review_at, next_review_after_result, start_of_utc_day, utc_now

REVIEW_TREND_DAYS = 14
REVIEW_RESULT_LABELS: dict[str, str] = {"good": "会了", "again": "再练练"}


async def get_or_create_settings(db: AsyncSession, user_id: str) -> UserReviewSettings:
    row = await db.get(UserReviewSettings, user_id)
    if row:
        return row
    row = UserReviewSettings(user_id=user_id)
    db.add(row)
    await db.flush()
    return row


async def ensure_mistake_review(db: AsyncSession, mistake: Mistake) -> MistakeReview:
    if not mistake.user_id:
        raise ValueError("错题缺少所属用户")
    existing = await db.execute(
        select(MistakeReview).where(MistakeReview.mistake_id == mistake.id)
    )
    rev = existing.scalar_one_or_none()
    if rev:
        return rev
    rev = MistakeReview(
        user_id=mistake.user_id,
        mistake_id=mistake.id,
        review_stage=0,
        next_review_at=initial_next_review_at(),
    )
    db.add(rev)
    await db.flush()
    return rev


def stem_preview(stem: str, max_len: int = 120) -> str:
    text = (stem or "").strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


async def settings_out(db: AsyncSession, settings: UserReviewSettings) -> dict:
    grade_name = None
    subject_name = None
    if settings.review_grade_level_id:
        g = await db.get(GradeLevel, settings.review_grade_level_id)
        grade_name = g.name if g else None
    if settings.review_subject_id:
        s = await db.get(Subject, settings.review_subject_id)
        subject_name = s.name if s else None
    return {
        "include_mastered_in_review": settings.include_mastered_in_review,
        "daily_review_target": settings.daily_review_target,
        "review_grade_level_id": settings.review_grade_level_id,
        "review_subject_id": settings.review_subject_id,
        "review_grade_name": grade_name,
        "review_subject_name": subject_name,
    }


async def compute_streak_days(db: AsyncSession, user_id: str) -> int:
    """连续打卡天数：含今天起向前连续有完成记录的日期数。"""
    today = utc_now().date()
    rows = (
        await db.execute(
            select(ReviewSession.review_date)
            .where(
                ReviewSession.user_id == user_id,
                ReviewSession.completed_count > 0,
            )
            .group_by(ReviewSession.review_date)
            .order_by(ReviewSession.review_date.desc())
        )
    ).all()
    dates = {r[0] for r in rows}
    if today not in dates:
        # 若今天尚未打卡，从昨天起算连续天数
        check = today - timedelta(days=1)
    else:
        check = today
    streak = 0
    while check in dates:
        streak += 1
        check -= timedelta(days=1)
    return streak


async def today_completed_count(db: AsyncSession, user_id: str) -> int:
    today = utc_now().date()
    result = await db.execute(
        select(func.coalesce(func.sum(ReviewSession.completed_count), 0)).where(
            ReviewSession.user_id == user_id,
            ReviewSession.review_date == today,
        )
    )
    return int(result.scalar_one())


async def get_or_create_today_session(
    db: AsyncSession,
    user_id: str,
    *,
    grade_level_id: str | None,
    subject_id: str | None,
) -> ReviewSession:
    today = utc_now().date()
    q = select(ReviewSession).where(
        ReviewSession.user_id == user_id,
        ReviewSession.review_date == today,
        ReviewSession.grade_level_id == grade_level_id,
        ReviewSession.subject_id == subject_id,
    )
    row = (await db.execute(q)).scalar_one_or_none()
    if row:
        return row
    row = ReviewSession(
        user_id=user_id,
        review_date=today,
        grade_level_id=grade_level_id,
        subject_id=subject_id,
        completed_count=0,
    )
    db.add(row)
    await db.flush()
    return row


async def record_review(
    db: AsyncSession,
    user: User,
    mistake_id: str,
    result: str,
    *,
    grade_level_id: str | None,
    subject_id: str | None,
) -> tuple[MistakeReview, int, int]:
    if result not in ("good", "again"):
        raise ValueError("复习结果无效")
    m = await db.get(Mistake, mistake_id)
    if not m or m.user_id != user.id:
        raise ValueError("错题不存在")
    rev = await ensure_mistake_review(db, m)
    stage, next_at = next_review_after_result(rev.review_stage, result)
    rev.review_stage = stage
    rev.next_review_at = next_at
    rev.last_reviewed_at = utc_now()
    rev.last_result = result

    session = await get_or_create_today_session(
        db, user.id, grade_level_id=grade_level_id, subject_id=subject_id
    )
    existing_item = await db.execute(
        select(ReviewSessionItem).where(
            ReviewSessionItem.session_id == session.id,
            ReviewSessionItem.mistake_id == mistake_id,
        )
    )
    if not existing_item.scalar_one_or_none():
        db.add(
            ReviewSessionItem(
                session_id=session.id,
                mistake_id=mistake_id,
                result=result,
            )
        )
        session.completed_count += 1

    await db.flush()
    streak = await compute_streak_days(db, user.id)
    completed = await today_completed_count(db, user.id)
    return rev, completed, streak


async def query_due_total(
    db: AsyncSession,
    user_id: str,
    *,
    include_mastered: bool,
) -> int:
    conditions = [
        Mistake.user_id == user_id,
        MistakeReview.next_review_at <= end_of_utc_day(),
    ]
    if not include_mastered:
        conditions.append(Mistake.is_mastered.is_(False))
    q = (
        select(func.count())
        .select_from(Mistake)
        .join(MistakeReview, MistakeReview.mistake_id == Mistake.id)
        .where(and_(*conditions))
    )
    return int((await db.execute(q)).scalar_one())


async def query_review_daily_trend(
    db: AsyncSession,
    user_id: str,
    *,
    days: int = REVIEW_TREND_DAYS,
) -> list[tuple[date, int]]:
    today = utc_now().date()
    since = today - timedelta(days=days - 1)
    q = (
        select(ReviewSession.review_date, func.count(ReviewSessionItem.id).label("cnt"))
        .join(ReviewSessionItem, ReviewSessionItem.session_id == ReviewSession.id)
        .where(ReviewSession.user_id == user_id, ReviewSession.review_date >= since)
        .group_by(ReviewSession.review_date)
    )
    rows = (await db.execute(q)).all()
    counts = {row[0]: int(row.cnt) for row in rows}
    return [(since + timedelta(days=i), counts.get(since + timedelta(days=i), 0)) for i in range(days)]


async def query_review_by_result(db: AsyncSession, user_id: str) -> list[tuple[str, int]]:
    q = (
        select(ReviewSessionItem.result, func.count(ReviewSessionItem.id).label("cnt"))
        .join(ReviewSession, ReviewSession.id == ReviewSessionItem.session_id)
        .where(ReviewSession.user_id == user_id)
        .group_by(ReviewSessionItem.result)
    )
    return [(str(row[0]), int(row.cnt)) for row in (await db.execute(q)).all()]
