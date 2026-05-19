"""错题错因枚举（前后端共用稳定 code）。"""

from typing import TypedDict


class ErrorReasonOption(TypedDict):
    code: str
    label: str


ERROR_REASON_OPTIONS: list[ErrorReasonOption] = [
    {"code": "reading", "label": "没看清题目"},
    {"code": "concept", "label": "知识没学会"},
    {"code": "method", "label": "解题思路错"},
    {"code": "careless", "label": "粗心算错了"},
]

VALID_ERROR_REASON_CODES: frozenset[str] = frozenset(o["code"] for o in ERROR_REASON_OPTIONS)

_LABEL_BY_CODE: dict[str, str] = {o["code"]: o["label"] for o in ERROR_REASON_OPTIONS}

# 已废弃 code → 合并后的 canonical code（展示与统计归并）
LEGACY_ERROR_REASON_MAP: dict[str, str] = {
    "formula": "method",
    "memory": "concept",
    "calculation": "careless",
}


def canonical_error_reason(code: str | None) -> str | None:
    if not code:
        return None
    c = str(code).strip()
    if not c:
        return None
    return LEGACY_ERROR_REASON_MAP.get(c, c)


def error_reason_label(code: str | None) -> str | None:
    if not code:
        return None
    canonical = canonical_error_reason(code)
    if canonical and canonical in _LABEL_BY_CODE:
        return _LABEL_BY_CODE[canonical]
    return _LABEL_BY_CODE.get(code)


def parse_error_reason(value: str | None) -> str:
    """校验并返回错因 code；空或非法时抛出 ValueError。"""
    if value is None:
        raise ValueError("请选择错因")
    code = canonical_error_reason(str(value).strip())
    if not code:
        raise ValueError("请选择错因")
    if code not in VALID_ERROR_REASON_CODES:
        raise ValueError("错因选项无效")
    return code
