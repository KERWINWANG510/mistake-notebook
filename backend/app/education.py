"""内置教育阶段（与 users.education_stage 存码一致）。"""

from datetime import date
from typing import Final

# (存库编码, 中文名)
EDUCATION_STAGES: Final[list[tuple[str, str]]] = [
    ("primary", "小学"),
    ("junior", "初中"),
    ("senior", "高中"),
    ("university", "大学"),
]

EDUCATION_CODES: Final[frozenset[str]] = frozenset(c for c, _ in EDUCATION_STAGES)

# 各教育阶段对应的年级 level 区间（与 grade_levels.level 一致）
STAGE_GRADE_RANGE: Final[dict[str, tuple[int, int]]] = {
    "primary": (1, 6),
    "junior": (7, 9),
    "senior": (10, 12),
}


def infer_current_grade_level(
    education_stage: str | None,
    enrollment_year: int | None,
    *,
    today: date | None = None,
) -> int | None:
    """根据教育阶段与入学年份推断当前年级序号（9 月为新学年起点）。"""
    if not education_stage or enrollment_year is None:
        return None
    bounds = STAGE_GRADE_RANGE.get(education_stage)
    if bounds is None:
        return None
    today = today or date.today()
    academic_start_year = today.year if today.month >= 9 else today.year - 1
    years_in_stage = academic_start_year - enrollment_year + 1
    if years_in_stage < 1:
        years_in_stage = 1
    lo, hi = bounds
    return max(lo, min(hi, lo + years_in_stage - 1))
