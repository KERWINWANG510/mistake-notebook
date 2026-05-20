"""错题列表组合筛选（参数化 SQL，禁止拼接用户输入）。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import Select, or_, text

from app.error_reasons import VALID_ERROR_REASON_CODES, canonical_error_reason
from app.models import Mistake


def escape_like_pattern(raw: str) -> str:
    return raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _normalize_tag_list(
    knowledge_tags: list[str] | None,
    knowledge_tag: str | None,
) -> list[str]:
    tags: list[str] = []
    if knowledge_tags:
        for t in knowledge_tags:
            s = (t or "").strip()
            if s and s not in tags:
                tags.append(s)
    if not tags and knowledge_tag:
        s = knowledge_tag.strip()
        if s:
            tags.append(s)
    return tags


def _parse_error_reason_codes(codes: list[str] | None) -> list[str]:
    if not codes:
        return []
    out: list[str] = []
    for raw in codes:
        c = canonical_error_reason((raw or "").strip())
        if c and c in VALID_ERROR_REASON_CODES and c not in out:
            out.append(c)
    return out


def apply_mistake_list_filters(
    stmt: Select,
    *,
    q: str | None = None,
    knowledge_tags: list[str] | None = None,
    knowledge_tag: str | None = None,
    tag_match: Literal["and", "or"] = "or",
    date_from: date | None = None,
    date_to: date | None = None,
    has_image: bool | None = None,
    error_reasons: list[str] | None = None,
    subject_id: str | None = None,
    grade_level_id: str | None = None,
    mastery: Literal["mastered", "unmastered", "all"] = "unmastered",
) -> Select:
    if subject_id:
        stmt = stmt.where(Mistake.subject_id == subject_id)
    if grade_level_id:
        stmt = stmt.where(Mistake.grade_level_id == grade_level_id)
    if mastery == "mastered":
        stmt = stmt.where(Mistake.is_mastered.is_(True))
    elif mastery == "unmastered":
        stmt = stmt.where(Mistake.is_mastered.is_(False))

    tags = _normalize_tag_list(knowledge_tags, knowledge_tag)
    if tags:
        if tag_match == "and":
            for tag in tags:
                stmt = stmt.where(
                    text(
                        "EXISTS (SELECT 1 FROM json_each(COALESCE(mistakes.knowledge_tags, '[]')) "
                        "WHERE json_each.value = :ktag)"
                    ).bindparams(ktag=tag)
                )
        else:
            clauses = [
                text(
                    "EXISTS (SELECT 1 FROM json_each(COALESCE(mistakes.knowledge_tags, '[]')) "
                    "WHERE json_each.value = :ktag)"
                ).bindparams(ktag=tag)
                for tag in tags
            ]
            stmt = stmt.where(or_(*clauses))

    reason_codes = _parse_error_reason_codes(error_reasons)
    if reason_codes:
        stmt = stmt.where(Mistake.error_reason.in_(reason_codes))

    if date_from is not None:
        start = datetime.combine(date_from, time.min)
        stmt = stmt.where(Mistake.created_at >= start)
    if date_to is not None:
        end_exclusive = datetime.combine(date_to + timedelta(days=1), time.min)
        stmt = stmt.where(Mistake.created_at < end_exclusive)

    if has_image is True:
        stmt = stmt.where(Mistake.image_path.is_not(None), Mistake.image_path != "")
    elif has_image is False:
        stmt = stmt.where(or_(Mistake.image_path.is_(None), Mistake.image_path == ""))

    search = (q or "").strip()
    if search:
        pattern = f"%{escape_like_pattern(search)}%"
        stmt = stmt.where(
            or_(
                Mistake.stem.like(pattern, escape="\\"),
                Mistake.analysis.like(pattern, escape="\\"),
                Mistake.answer.like(pattern, escape="\\"),
                text(
                    "EXISTS (SELECT 1 FROM json_each(COALESCE(mistakes.knowledge_tags, '[]')) "
                    "WHERE json_each.value LIKE :qpat ESCAPE '\\')"
                ).bindparams(qpat=pattern),
            )
        )

    return stmt
