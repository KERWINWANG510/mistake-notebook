"""模拟卷题型：按科目编码与年级（1–12）筛选可用题型。"""

from __future__ import annotations

# 题型编码 -> 展示名（与前端、出题 JSON 一致）
QUESTION_TYPE_LABELS: dict[str, str] = {
    "single_choice": "单选题",
    "multiple_choice": "多选题",
    "fill_blank": "填空题",
    "true_false": "判断题",
    "short_answer": "简答题",
    "calculation": "计算题",
    "reading": "阅读理解",
    "cloze": "完形填空",
    "writing": "写作题",
    "essay": "作文题",
    "material_analysis": "材料分析题",
    "experimental": "实验探究题",
}

# 无科目编码（自定义科目）时的通用题型
_FALLBACK_CODES = ("single_choice", "multiple_choice", "fill_blank", "true_false", "short_answer")


def _base_science(level: int) -> list[str]:
    codes = ["single_choice", "multiple_choice", "fill_blank", "true_false", "short_answer"]
    if level >= 8:
        codes.append("experimental")
    if level >= 7:
        codes.append("calculation")
    return codes


def question_type_codes_for(subject_code: str | None, grade_level: int) -> list[str]:
    """返回该年级、科目下可选题型编码列表（有序、去重）。"""
    lv = max(1, min(12, int(grade_level)))
    code = (subject_code or "").strip().lower() or None

    if not code:
        return list(_FALLBACK_CODES)

    if code == "math":
        return ["single_choice", "multiple_choice", "fill_blank", "true_false", "calculation", "short_answer"]

    if code == "chinese":
        out = ["single_choice", "multiple_choice", "fill_blank", "true_false", "reading", "short_answer"]
        if lv >= 3:
            out.append("essay")
        return out

    if code == "english":
        out = ["single_choice", "fill_blank", "true_false", "reading", "short_answer"]
        if lv >= 5:
            out.insert(3, "cloze")
        if lv >= 7:
            out.append("writing")
        return out

    if code in {"politics", "history", "geography"}:
        out = ["single_choice", "multiple_choice", "fill_blank", "true_false", "short_answer"]
        if lv >= 7:
            out.append("material_analysis")
        return out

    if code in {"physics", "chemistry", "biology"}:
        return _base_science(lv)

    return list(_FALLBACK_CODES)


def question_type_label(code: str) -> str:
    return QUESTION_TYPE_LABELS.get(code, code)


def is_known_type(code: str) -> bool:
    return code in QUESTION_TYPE_LABELS
