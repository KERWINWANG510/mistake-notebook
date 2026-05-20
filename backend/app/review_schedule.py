"""错题复习间隔调度（固定阶梯，非 SM-2）。"""

from datetime import datetime, timedelta

# 掌握后各阶段间隔（天）：第 1 次复习后 → 3 天 → 7 天 → 14 天 → 30 天
REVIEW_INTERVALS_DAYS = (1, 3, 7, 14, 30)


def utc_now() -> datetime:
    return datetime.utcnow()


def start_of_utc_day(dt: datetime | None = None) -> datetime:
    t = dt or utc_now()
    return datetime(t.year, t.month, t.day)


def end_of_utc_day(dt: datetime | None = None) -> datetime:
    return start_of_utc_day(dt) + timedelta(days=1) - timedelta(microseconds=1)


def initial_next_review_at() -> datetime:
    """新错题：当天即可进入「今日复习」待复习队列（UTC 日界）。"""
    return start_of_utc_day(utc_now())


def next_review_after_result(stage: int, result: str) -> tuple[int, datetime]:
    """
    根据本次结果计算下一阶段与下次复习时间。
    result: good | again
    """
    if result == "again":
        return 0, start_of_utc_day(utc_now()) + timedelta(days=1)
    new_stage = min(stage + 1, len(REVIEW_INTERVALS_DAYS) - 1)
    days = REVIEW_INTERVALS_DAYS[new_stage]
    return new_stage, start_of_utc_day(utc_now()) + timedelta(days=days)
