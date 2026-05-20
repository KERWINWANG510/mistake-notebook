"""复习计划：今日队列、打卡、通用设置。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models import GradeLevel, Mistake, MistakeReview, ReviewSession, ReviewSessionItem, Subject, User
from app.review_helpers import (
    compute_streak_days,
    get_or_create_settings,
    record_review,
    settings_out,
    stem_preview,
    today_completed_count,
)
from app.review_schedule import end_of_utc_day
from app.routers.deps import get_current_user
from app.schemas import (
    ReviewRecordBody,
    ReviewRecordOut,
    ReviewSettingsOut,
    ReviewSettingsUpdate,
    ReviewStatsOut,
    ReviewTodayItemOut,
    ReviewTodayOut,
)

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("/settings", response_model=ReviewSettingsOut)
async def get_review_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewSettingsOut:
    settings = await get_or_create_settings(db, user.id)
    return ReviewSettingsOut(**await settings_out(db, settings))


@router.patch("/settings", response_model=ReviewSettingsOut)
async def update_review_settings(
    body: ReviewSettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewSettingsOut:
    settings = await get_or_create_settings(db, user.id)
    if body.include_mastered_in_review is not None:
        settings.include_mastered_in_review = body.include_mastered_in_review
    if body.daily_review_target is not None:
        settings.daily_review_target = body.daily_review_target
    if body.review_grade_level_id is not None:
        if body.review_grade_level_id and not await db.get(GradeLevel, body.review_grade_level_id):
            raise HTTPException(status_code=400, detail="年级不存在")
        settings.review_grade_level_id = body.review_grade_level_id or None
    if body.review_subject_id is not None:
        if body.review_subject_id and not await db.get(Subject, body.review_subject_id):
            raise HTTPException(status_code=400, detail="科目不存在")
        settings.review_subject_id = body.review_subject_id or None
    await db.commit()
    await db.refresh(settings)
    return ReviewSettingsOut(**await settings_out(db, settings))


@router.get("/today", response_model=ReviewTodayOut)
async def review_today(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    grade_level_id: str | None = Query(None, description="覆盖设置中的年级筛选"),
    subject_id: str | None = Query(None, description="覆盖设置中的科目筛选"),
) -> ReviewTodayOut:
    settings = await get_or_create_settings(db, user.id)
    if grade_level_id is not None:
        if grade_level_id and not await db.get(GradeLevel, grade_level_id):
            raise HTTPException(status_code=400, detail="年级不存在")
        settings.review_grade_level_id = grade_level_id or None
    if subject_id is not None:
        if subject_id and not await db.get(Subject, subject_id):
            raise HTTPException(status_code=400, detail="科目不存在")
        settings.review_subject_id = subject_id or None
    if grade_level_id is not None or subject_id is not None:
        await db.commit()

    conditions = [
        Mistake.user_id == user.id,
        MistakeReview.next_review_at <= end_of_utc_day(),
    ]
    if not settings.include_mastered_in_review:
        conditions.append(Mistake.is_mastered.is_(False))
    if settings.review_grade_level_id:
        conditions.append(Mistake.grade_level_id == settings.review_grade_level_id)
    if settings.review_subject_id:
        conditions.append(Mistake.subject_id == settings.review_subject_id)

    q = (
        select(Mistake, MistakeReview)
        .join(MistakeReview, MistakeReview.mistake_id == Mistake.id)
        .options(joinedload(Mistake.subject), joinedload(Mistake.grade))
        .where(and_(*conditions))
        .order_by(MistakeReview.next_review_at.asc(), Mistake.created_at.asc())
    )
    pairs = (await db.execute(q)).unique().all()
    due_total = len(pairs)
    target = settings.daily_review_target
    items: list[ReviewTodayItemOut] = []
    for m, rev in pairs[:target]:
        items.append(
            ReviewTodayItemOut(
                mistake_id=m.id,
                subject_id=m.subject_id,
                grade_level_id=m.grade_level_id,
                subject_name=m.subject.name if m.subject else None,
                grade_name=m.grade.name if m.grade else None,
                stem_preview=stem_preview(m.stem),
                analysis=m.analysis or "",
                answer=m.answer or "",
                is_mastered=m.is_mastered,
                review_stage=rev.review_stage,
                next_review_at=rev.next_review_at,
                image_path=m.image_path,
            )
        )

    streak = await compute_streak_days(db, user.id)
    completed = await today_completed_count(db, user.id)
    return ReviewTodayOut(
        daily_target=target,
        due_total=due_total,
        today_completed=completed,
        streak_days=streak,
        items=items,
        settings=ReviewSettingsOut(**await settings_out(db, settings)),
    )


@router.post("/record", response_model=ReviewRecordOut)
async def submit_review_record(
    body: ReviewRecordBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewRecordOut:
    settings = await get_or_create_settings(db, user.id)
    grade_id = body.grade_level_id if body.grade_level_id is not None else settings.review_grade_level_id
    subject_id = body.subject_id if body.subject_id is not None else settings.review_subject_id
    try:
        rev, completed, streak = await record_review(
            db,
            user,
            body.mistake_id,
            body.result,
            grade_level_id=grade_id,
            subject_id=subject_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return ReviewRecordOut(
        mistake_id=body.mistake_id,
        review_stage=rev.review_stage,
        next_review_at=rev.next_review_at,
        today_completed=completed,
        streak_days=streak,
    )


@router.get("/stats", response_model=ReviewStatsOut)
async def review_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewStatsOut:
    settings = await get_or_create_settings(db, user.id)
    conditions = [
        Mistake.user_id == user.id,
        MistakeReview.next_review_at <= end_of_utc_day(),
    ]
    if not settings.include_mastered_in_review:
        conditions.append(Mistake.is_mastered.is_(False))
    if settings.review_grade_level_id:
        conditions.append(Mistake.grade_level_id == settings.review_grade_level_id)
    if settings.review_subject_id:
        conditions.append(Mistake.subject_id == settings.review_subject_id)

    due_q = (
        select(func.count())
        .select_from(Mistake)
        .join(MistakeReview, MistakeReview.mistake_id == Mistake.id)
        .where(and_(*conditions))
    )
    due_total = int((await db.execute(due_q)).scalar_one())

    total_q = (
        select(func.count())
        .select_from(ReviewSessionItem)
        .join(ReviewSession, ReviewSession.id == ReviewSessionItem.session_id)
        .where(ReviewSession.user_id == user.id)
    )
    total_reviewed = int((await db.execute(total_q)).scalar_one())

    streak = await compute_streak_days(db, user.id)
    completed = await today_completed_count(db, user.id)
    return ReviewStatsOut(
        streak_days=streak,
        today_completed=completed,
        daily_target=settings.daily_review_target,
        due_total=due_total,
        total_reviewed_all_time=total_reviewed,
    )
