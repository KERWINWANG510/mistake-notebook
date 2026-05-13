"""内置教育阶段（与 users.education_stage 存码一致）。"""

from typing import Final

# (存库编码, 中文名)
EDUCATION_STAGES: Final[list[tuple[str, str]]] = [
    ("primary", "小学"),
    ("junior", "初中"),
    ("senior", "高中"),
    ("university", "大学"),
]

EDUCATION_CODES: Final[frozenset[str]] = frozenset(c for c, _ in EDUCATION_STAGES)
