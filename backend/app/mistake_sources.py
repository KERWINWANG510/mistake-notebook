"""错题来源枚举（前后端共用稳定 code）。"""

from typing import TypedDict


class MistakeSourceOption(TypedDict):
    code: str
    label: str


MISTAKE_SOURCE_OPTIONS: list[MistakeSourceOption] = [
    {"code": "homework", "label": "作业"},
    {"code": "monthly_exam", "label": "月考"},
    {"code": "real_exam", "label": "真题"},
]

VALID_MISTAKE_SOURCE_CODES: frozenset[str] = frozenset(o["code"] for o in MISTAKE_SOURCE_OPTIONS)

_LABEL_BY_CODE: dict[str, str] = {o["code"]: o["label"] for o in MISTAKE_SOURCE_OPTIONS}


def mistake_source_label(code: str | None) -> str | None:
    if not code:
        return None
    return _LABEL_BY_CODE.get(str(code).strip())


def parse_mistake_source(value: str | None) -> str:
    """校验并返回错题来源 code；空或非法时抛出 ValueError。"""
    if value is None:
        raise ValueError("请选择错题来源")
    code = str(value).strip()
    if not code:
        raise ValueError("请选择错题来源")
    if code not in VALID_MISTAKE_SOURCE_CODES:
        raise ValueError("错题来源选项无效")
    return code
