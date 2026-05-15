import base64
import json
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.knowledge_tags import normalize_knowledge_tags
from app.mock_paper_types import question_type_codes_for, question_type_label
from app.models import AiProviderConfig, GradeLevel, GradeSubject, Mistake, Subject, User
from app.routers.analyze import _solve_transport, _strip_json_fence, _vision_transport
from app.routers.deps import get_current_user
from app.routers.mistakes import _require_owner
from app.schemas import (
    MockPaperAnswerOut,
    MockPaperGenerateBody,
    MockPaperGenerateResult,
    MockPaperItemOut,
    MockPaperQuestionTypeItem,
    MockPaperSectionOut,
    PracticeCheckResult,
    PracticeDifficulty,
    PracticeGenerateBody,
    PracticeGenerateResult,
)
from app.services.ai_client import UpstreamChatError, chat_completion, chat_completion_stream

router = APIRouter(prefix="/api/practice", tags=["practice"])

_DIFFICULTY_LABELS: dict[str, str] = {
    "easy": "简单",
    "medium": "适中",
    "hard": "困难",
    "challenge": "挑战",
}


def _parse_json_object(content: str, label: str) -> dict:
    raw = _strip_json_fence(content)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"{label}返回不是合法 JSON: {e}") from e
    if not isinstance(obj, dict):
        raise HTTPException(status_code=502, detail=f"{label}返回格式异常")
    return obj


async def _active_cfg(db: AsyncSession) -> AiProviderConfig:
    r = await db.execute(select(AiProviderConfig).where(AiProviderConfig.is_active.is_(True)))
    cfg = r.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=409, detail="未配置或未激活 AI，请先在设置中完成配置")
    return cfg


async def _load_mistake(db: AsyncSession, mistake_id: str, user: User) -> Mistake:
    r = await db.execute(
        select(Mistake)
        .options(joinedload(Mistake.subject), joinedload(Mistake.grade))
        .where(Mistake.id == mistake_id)
    )
    return _require_owner(r.scalar_one_or_none(), user)


def _generate_system_prompt(difficulty: PracticeDifficulty) -> str:
    label = _DIFFICULTY_LABELS[difficulty]
    return (
        "你是中小学出题助手。用户给出某道错题（题干、解题思路、答案、科目与年级）。"
        f"请出一道**同类型、同知识点**的练习题，难度为「{label}」。"
        "要求：情境或数据应变化，不可照抄原题；表述适合对应年级；题目应可独立作答。"
        "只输出一个 JSON 对象，不要 Markdown 代码块。字段为："
        "question_stem（新题题干，纯文本）, "
        "reference_answer（参考答案，含单位）, "
        "reference_analysis（简要解题思路，可用 **加粗** 与换行）。"
    )


def _check_system_prompt() -> str:
    return (
        "你是中小学作业批改助手。用户给出练习题、参考答案与学生的作答（可能来自文字或识图）。"
        "请判断学生作答是否正确，并给出简明反馈。"
        "只输出一个 JSON 对象，不要 Markdown 代码块。字段为："
        "verdict（correct / partial / wrong 三选一）, "
        "feedback（给学生看的评语，2～5 句，指出对错与改进建议）, "
        "standard_answer（标准答案，可与参考一致或略整理）, "
        "explanation（解题讲解，分步简明说明）。"
    )


async def _ocr_answer_image(cfg: AiProviderConfig, data: bytes, ctype: str) -> str:
    v_base, v_chat, v_key = _vision_transport(cfg)
    if not v_key:
        raise HTTPException(status_code=409, detail="识图步骤缺少可用的 API Key")

    vision_model = cfg.selected_model_vision or cfg.selected_model
    if not vision_model:
        raise HTTPException(status_code=400, detail="请配置识图模型")

    b64 = base64.standard_b64encode(data).decode("ascii")
    data_url = f"data:{ctype};base64,{b64}"
    ocr_system = (
        "你是 OCR 助手。请识别学生手写作答内容（含公式尽量用 LaTeX 或纯文本）。"
        "只输出一个 JSON 对象，字段仅包含 answer_text（字符串，无内容则空字符串）。"
    )
    ocr_user: list[dict] = [
        {"type": "text", "text": "请识别图片中的学生作答。"},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]
    ok, content, _ = await chat_completion(
        v_base,
        v_chat,
        v_key,
        vision_model,
        [{"role": "system", "content": ocr_system}, {"role": "user", "content": ocr_user}],
        temperature=0.1,
    )
    if not ok or content is None:
        raise HTTPException(status_code=502, detail=content or "识图模型调用失败")

    obj = _parse_json_object(content, "识图模型")
    text = obj.get("answer_text", "")
    return text.strip() if isinstance(text, str) else ""


@router.post("/generate", response_model=PracticeGenerateResult)
async def generate_practice(
    body: PracticeGenerateBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PracticeGenerateResult:
    cfg = await _active_cfg(db)
    mistake = await _load_mistake(db, body.mistake_id, user)

    s_base, s_chat, s_key = _solve_transport(cfg)
    if not s_key:
        raise HTTPException(status_code=409, detail="解题步骤缺少可用的 API Key")

    solve_model = cfg.selected_model_solve or cfg.selected_model
    if not solve_model:
        raise HTTPException(status_code=400, detail="请配置解题模型")

    subject_name = mistake.subject.name if mistake.subject else "未知科目"
    grade_name = mistake.grade.name if mistake.grade else "未知年级"
    user_content = (
        f"科目：{subject_name}\n年级：{grade_name}\n"
        f"原题题干：\n{mistake.stem}\n\n"
        f"原题解题思路：\n{mistake.analysis}\n\n"
        f"原题答案：\n{mistake.answer}\n"
    )
    messages = [
        {"role": "system", "content": _generate_system_prompt(body.difficulty)},
        {"role": "user", "content": user_content},
    ]
    ok, content, _ = await chat_completion(s_base, s_chat, s_key, solve_model, messages, temperature=0.35)
    if not ok or content is None:
        raise HTTPException(status_code=502, detail=content or "出题模型调用失败")

    obj = _parse_json_object(content, "出题模型")
    stem = str(obj.get("question_stem", "")).strip()
    if not stem:
        raise HTTPException(status_code=502, detail="出题结果缺少题干")
    return PracticeGenerateResult(
        question_stem=stem,
        reference_answer=str(obj.get("reference_answer", "")).strip(),
        reference_analysis=str(obj.get("reference_analysis", "")).strip(),
    )


@router.post("/check", response_model=PracticeCheckResult)
async def check_practice(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    mistake_id: str = Form(...),
    question_stem: str = Form(...),
    reference_answer: str = Form(...),
    reference_analysis: str = Form(""),
    user_answer: str = Form(""),
    file: UploadFile | None = File(None),
) -> PracticeCheckResult:
    if not question_stem.strip():
        raise HTTPException(status_code=400, detail="题目不能为空")

    cfg = await _active_cfg(db)
    await _load_mistake(db, mistake_id, user)

    answer_parts: list[str] = []
    if user_answer.strip():
        answer_parts.append(user_answer.strip())

    if file is not None and file.filename:
        data = await file.read()
        if len(data) > 15 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="图片过大，请压缩后重试（最大约 15MB）")
        ctype = file.content_type or "image/jpeg"
        if not ctype.startswith("image/"):
            raise HTTPException(status_code=400, detail="请上传图片文件")
        ocr_text = await _ocr_answer_image(cfg, data, ctype)
        if ocr_text:
            answer_parts.append(ocr_text)

    combined_answer = "\n".join(answer_parts).strip()
    if not combined_answer:
        raise HTTPException(status_code=400, detail="请填写作答或上传作答图片")

    s_base, s_chat, s_key = _solve_transport(cfg)
    if not s_key:
        raise HTTPException(status_code=409, detail="解题步骤缺少可用的 API Key")

    solve_model = cfg.selected_model_solve or cfg.selected_model
    if not solve_model:
        raise HTTPException(status_code=400, detail="请配置解题模型")

    user_content = (
        f"练习题题干：\n{question_stem.strip()}\n\n"
        f"参考解题思路：\n{reference_analysis.strip() or '（无）'}\n\n"
        f"参考答案：\n{reference_answer.strip() or '（无）'}\n\n"
        f"学生作答：\n{combined_answer}\n"
    )
    messages = [
        {"role": "system", "content": _check_system_prompt()},
        {"role": "user", "content": user_content},
    ]
    ok, content, _ = await chat_completion(s_base, s_chat, s_key, solve_model, messages, temperature=0.2)
    if not ok or content is None:
        raise HTTPException(status_code=502, detail=content or "批改模型调用失败")

    obj = _parse_json_object(content, "批改模型")
    verdict = str(obj.get("verdict", "wrong")).strip().lower()
    if verdict not in {"correct", "partial", "wrong"}:
        verdict = "wrong"
    return PracticeCheckResult(
        verdict=verdict,
        feedback=str(obj.get("feedback", "")).strip() or "已完成批改。",
        standard_answer=str(obj.get("standard_answer", reference_answer)).strip(),
        explanation=str(obj.get("explanation", "")).strip(),
    )


_MAX_MOCK_QUESTIONS = 28


def _ndline(obj: dict) -> bytes:
    return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")


@dataclass
class MockPaperGenContext:
    """组卷生成所需的已解析上下文（不含上游原始响应）。"""

    grade: GradeLevel
    subject: Subject
    active_types: list[str]
    total_score: int
    use_answer_sheet: bool
    messages: list[dict[str, Any]]
    solve_base: str
    solve_chat: str
    solve_key: str | None
    solve_model: str


def _http_exc_detail(exc: HTTPException) -> str:
    d = exc.detail
    return d if isinstance(d, str) else str(d)


async def _mock_paper_load_context(db: AsyncSession, body: MockPaperGenerateBody) -> MockPaperGenContext:
    cfg = await _active_cfg(db)
    grade, subject = await _resolve_grade_subject(db, body.grade_level_id, body.subject_id)

    allowed_ordered = question_type_codes_for(subject.code, grade.level)
    allowed_set = set(allowed_ordered)

    raw_pick = _dedupe_preserve([str(x) for x in body.question_type_codes])
    if raw_pick:
        invalid = [c for c in raw_pick if c not in allowed_set]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail="存在不适用当前年级、科目的题型：" + "、".join(invalid),
            )
        active_types = raw_pick
    else:
        active_types = list(allowed_ordered)

    tags = normalize_knowledge_tags([str(t) for t in body.knowledge_tags])
    counts = _sanitize_counts_by_type(body.counts_by_type, set(active_types))
    total_score = int(body.total_score) if body.total_score is not None else 100

    s_base, s_chat, s_key = _solve_transport(cfg)
    if not s_key:
        raise HTTPException(status_code=409, detail="解题步骤缺少可用的 API Key")
    solve_model = cfg.selected_model_solve or cfg.selected_model
    if not solve_model:
        raise HTTPException(status_code=400, detail="请配置解题模型")

    user_msg = _build_mock_paper_user_message(
        grade_name=grade.name,
        subject_name=subject.name,
        subject_code=subject.code,
        grade_level=grade.level,
        tags=tags,
        active_type_codes=active_types,
        counts_by_type=counts,
        total_score=total_score,
        use_answer_sheet=bool(body.use_answer_sheet),
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _mock_paper_system_prompt(bool(body.use_answer_sheet))},
        {"role": "user", "content": user_msg},
    ]
    return MockPaperGenContext(
        grade=grade,
        subject=subject,
        active_types=active_types,
        total_score=total_score,
        use_answer_sheet=bool(body.use_answer_sheet),
        messages=messages,
        solve_base=s_base,
        solve_chat=s_chat,
        solve_key=s_key,
        solve_model=solve_model,
    )


def _mock_paper_build_result_from_content(
    content: str,
    *,
    ctx: MockPaperGenContext,
) -> MockPaperGenerateResult:
    obj = _parse_json_object(content, "模拟卷")
    title = str(obj.get("title", "")).strip() or f"{ctx.grade.name}{ctx.subject.name}模拟练习"
    instructions = str(obj.get("instructions", "")).strip()
    sections, answers = _parse_mock_paper_document(obj, set(ctx.active_types))
    actual_total = sum(it.score for sec in sections for it in sec.items)
    n_q = sum(len(sec.items) for sec in sections)
    suggested_min = _parse_suggested_exam_minutes(obj, n_questions=n_q)
    return MockPaperGenerateResult(
        title=title,
        grade_name=ctx.grade.name,
        subject_name=ctx.subject.name,
        requested_total_score=ctx.total_score,
        actual_total_score=actual_total,
        suggested_exam_minutes=suggested_min,
        use_answer_sheet=ctx.use_answer_sheet,
        instructions=instructions,
        sections=sections,
        answers=answers,
    )


def _dedupe_preserve(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in seq:
        s = str(x).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _sanitize_counts_by_type(raw: dict[str, int] | None, allowed: set[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    if not raw:
        return out
    for k, v in raw.items():
        key = str(k).strip()
        if key not in allowed:
            continue
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= 20:
            out[key] = n
    return out


async def _resolve_grade_subject(
    db: AsyncSession, grade_level_id: str, subject_id: str
) -> tuple[GradeLevel, Subject]:
    gr = (await db.execute(select(GradeLevel).where(GradeLevel.id == grade_level_id))).scalar_one_or_none()
    if gr is None:
        raise HTTPException(status_code=404, detail="年级不存在")
    su = (await db.execute(select(Subject).where(Subject.id == subject_id))).scalar_one_or_none()
    if su is None:
        raise HTTPException(status_code=404, detail="科目不存在")
    gs = (
        await db.execute(
            select(GradeSubject).where(
                GradeSubject.grade_level_id == grade_level_id,
                GradeSubject.subject_id == subject_id,
            )
        )
    ).scalar_one_or_none()
    if gs is None:
        raise HTTPException(status_code=400, detail="该年级未关联此科目，请在「年级科目」中确认课表")
    return gr, su


def _parse_suggested_exam_minutes(obj: dict, *, n_questions: int) -> int:
    """解析 AI 建议考试时间（分钟）；缺失时按题量估算。"""
    raw = obj.get("suggested_exam_minutes")
    try:
        v = int(raw)
    except (TypeError, ValueError):
        v = 0
    if v < 1:
        v = max(25, min(90, round(n_questions * 2.5))) if n_questions else 60
    return max(10, min(240, v))


def _mock_paper_system_prompt(use_answer_sheet: bool) -> str:
    sheet_mode = (
        "本次组卷将配套「答题卡」页面由系统排版：各小题 stem 中**不要**预留大面积手写空白或整段「答：____」作答区；"
        "选择题仅在 stem 中写清题干与选项字母；填空题用题干内下划线标空即可；主观题题干简练，勿在 stem 末尾附多行横线。"
        if use_answer_sheet
        else "本次组卷**不使用**答题卡，考生直接在试卷上作答：每道小题 stem 末尾须留出**清晰可见的作答空间**"
        "（如换行后写「答：」并附与分值、题型匹配的横线或空白，主观题至少 3～6 行书写区；选择题可仅写选项无需大空白）。"
    )
    return (
        "你是中小学命题教师。请根据用户要求生成一份「模拟练习卷」（仅练习题，不要真实考试卷名或涉密内容）。"
        "题目应贴合年级认知与科目特点；表述清晰、可独立印刷作答；结构须与真实纸笔考试一致（按大题分区）。"
        "题干 stem 可使用换行分段、**加粗**；选择题请把选项完整写在 stem 内（如 A. B. C. D.）。"
        "考生填写姓名、年级、学号的横线由系统在卷首统一印刷，你不要在 JSON 中输出这些字段。"
        + sheet_mode
        + "只输出一个 JSON 对象，不要 Markdown 代码块。字段为："
        'title（试卷标题，字符串）, '
        'instructions（卷首说明或注意事项，可为空字符串）, '
        "suggested_exam_minutes（整数，建议考生完成本卷的作答时间，单位分钟，须结合年级、题量与难度给出合理值，常见约 40～100）, "
        "sections（大题数组，每项含："
        "section_order 整数从 1 递增；"
        "heading 字符串，完整大题标题行，须含大题序号与分值说明，例如「第一大题  选择题（本大题共24分）」；"
        "section_score 整数，该大题总分，须等于该大题下各小题 score 之和；"
        "questions 数组，该大题下的小题，每项含："
        "number 全局题号从 1 开始连续递增（跨大题连续）；"
        "minor_index 整数，该大题内小题序号从 1 递增（可选但推荐）；"
        "type_code 题型编码；score 小题分值；stem 题干字符串"
        "）, "
        'answers（数组，每项含 number 与全局题号对应、answer 参考答案或要点）。'
        "要求：所有大题 questions 中 number 从 1 到 N 连续不重复；每题 type_code 须为允许的编码；"
        f"小题总数不超过 {_MAX_MOCK_QUESTIONS} 道；各大题须有小题若干且 heading 须体现「第几大题」与题型或内容类型；"
        "各小题 score 之和应等于用户给定卷面总分（可在 ±2 分内微调为整数）；不得输出 JSON 以外的文字。"
    )


def _build_mock_paper_user_message(
    *,
    grade_name: str,
    subject_name: str,
    subject_code: str | None,
    grade_level: int,
    tags: list[str],
    active_type_codes: list[str],
    counts_by_type: dict[str, int],
    total_score: int,
    use_answer_sheet: bool,
) -> str:
    type_lines = [f"- {c}（{question_type_label(c)}）" for c in active_type_codes]
    counts_lines: list[str] = []
    for code, n in sorted(counts_by_type.items(), key=lambda x: x[0]):
        counts_lines.append(f"- {question_type_label(code)}：{n} 道")

    parts = [
        f"年级：{grade_name}（内部 level={grade_level}，命题时勿照抄此说明）",
        f"科目：{subject_name}",
        f"卷面总分：{total_score} 分",
        f"是否使用答题卡（由系统排版作答区）：{'是' if use_answer_sheet else '否'}。请严格按系统说明中的作答区要求编写 stem。",
        "允许使用的题型编码 type_code 必须且只能从下列之中选取（每题一项）：",
        "\n".join(type_lines),
    ]
    if tags:
        parts.append("知识点侧重（可适当体现，不必每题都点题）：" + "、".join(tags))
    if counts_lines:
        parts.append("用户对各题型题量的期望（尽量满足，若与总分或篇幅冲突可微调并仍用允许 type_code）：")
        parts.append("\n".join(counts_lines))
    else:
        parts.append("用户未指定各题型题量：请自行搭配合理题量，覆盖所选题型中的主要类型。")
    parts.append(
        "请使用 sections 输出至少 2 个大题（如选择、填空、解答等），每道小题放在对应大题的 questions 中，"
        "并在 heading 中标明本大题共多少分；勿再使用扁平的 items 字段（除非仅能出一道大题时再退化为单大题）。"
    )
    parts.append(
        "若用户未勾选全部允许题型，则仅使用其已勾选的题型编码组卷；"
        "若已勾选多种题型，请尽量覆盖多种，避免单一题型占比过高。"
    )
    return "\n\n".join(parts)


def _parse_one_question_dict(
    it: dict,
    *,
    allowed_type_codes: set[str],
    label: str,
) -> MockPaperItemOut:
    if not isinstance(it, dict):
        raise HTTPException(status_code=502, detail=f"{label}格式错误")
    try:
        num = int(it.get("number"))
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=502, detail=f"{label}题号无效") from e
    if num < 1 or num > 99:
        raise HTTPException(status_code=502, detail=f"{label}题号超出范围")
    mi_raw = it.get("minor_index")
    minor_index: int | None = None
    if mi_raw is not None and mi_raw != "":
        try:
            mi = int(mi_raw)
            if 1 <= mi <= 99:
                minor_index = mi
        except (TypeError, ValueError):
            minor_index = None
    tc = str(it.get("type_code", "")).strip()
    if tc not in allowed_type_codes:
        raise HTTPException(status_code=502, detail=f"题目 {num} 的题型「{tc}」不在当前组卷范围内")
    try:
        sc = int(it.get("score", 0))
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=502, detail=f"题目 {num} 分值无效") from e
    stem = str(it.get("stem", "")).strip()
    if not stem:
        raise HTTPException(status_code=502, detail=f"题目 {num} 题干为空")
    if len(stem) > 12000:
        raise HTTPException(status_code=502, detail=f"题目 {num} 题干过长")
    return MockPaperItemOut(
        number=num,
        minor_index=minor_index,
        type_code=tc,
        type_name=question_type_label(tc),
        score=max(0, min(200, sc)),
        stem=stem,
    )


def _answers_map_from_raw(raw_answers: object) -> dict[int, str]:
    ans_by_num: dict[int, str] = {}
    if isinstance(raw_answers, list):
        for a in raw_answers:
            if not isinstance(a, dict):
                continue
            try:
                n = int(a.get("number"))
            except (TypeError, ValueError):
                continue
            ans_by_num[n] = str(a.get("answer", "")).strip()
    return ans_by_num


def _answers_list_for_items(items: list[MockPaperItemOut], ans_by_num: dict[int, str]) -> list[MockPaperAnswerOut]:
    return [MockPaperAnswerOut(number=it.number, answer=ans_by_num.get(it.number, "（未提供）")) for it in items]


def _normalize_mock_paper_sections(sections: list[MockPaperSectionOut]) -> list[MockPaperSectionOut]:
    """按大题序号排序，并令 section_score 与各小题分值之和一致。"""
    indexed = sorted(enumerate(sections), key=lambda x: (x[1].section_order, x[0]))
    out: list[MockPaperSectionOut] = []
    for new_ord, (_i, sec) in enumerate(indexed, start=1):
        sum_sc = sum(it.score for it in sec.items)
        out.append(
            sec.model_copy(
                update={
                    "section_order": new_ord,
                    "section_score": sum_sc,
                }
            )
        )
    return out


def _parse_mock_paper_items(
    obj: dict,
    allowed_type_codes: set[str],
) -> tuple[list[MockPaperSectionOut], list[MockPaperAnswerOut]]:
    """兼容旧版扁平 items：整卷作为单一大题。"""
    raw_items = obj.get("items")
    raw_answers = obj.get("answers")
    if not isinstance(raw_items, list) or not raw_items:
        raise HTTPException(status_code=502, detail="出题结果缺少 items 或 sections")
    if len(raw_items) > _MAX_MOCK_QUESTIONS:
        raise HTTPException(status_code=502, detail=f"题目数量超过上限（{_MAX_MOCK_QUESTIONS}）")

    parsed_items: list[MockPaperItemOut] = []
    for idx, it in enumerate(raw_items):
        q = _parse_one_question_dict(it, allowed_type_codes=allowed_type_codes, label=f"题目第 {idx + 1} 项")
        if q.minor_index is None:
            q = q.model_copy(update={"minor_index": idx + 1})
        parsed_items.append(q)

    nums = [it.number for it in parsed_items]
    if len(nums) != len(set(nums)):
        raise HTTPException(status_code=502, detail="题号存在重复")
    if sorted(nums) != list(range(1, len(nums) + 1)):
        raise HTTPException(status_code=502, detail="题号必须从 1 开始连续递增")

    ans_by_num = _answers_map_from_raw(raw_answers)
    answers = _answers_list_for_items(parsed_items, ans_by_num)
    sec_score = sum(it.score for it in parsed_items)
    section = MockPaperSectionOut(
        section_order=1,
        heading="习题",
        section_score=sec_score,
        items=parsed_items,
    )
    return [section], answers


def _parse_mock_paper_sections(
    obj: dict,
    allowed_type_codes: set[str],
) -> tuple[list[MockPaperSectionOut], list[MockPaperAnswerOut]]:
    raw_sections = obj.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise HTTPException(status_code=502, detail="出题结果缺少 sections")
    if len(raw_sections) > 20:
        raise HTTPException(status_code=502, detail="大题数量过多")

    sections: list[MockPaperSectionOut] = []
    all_items: list[MockPaperItemOut] = []

    for sidx, sec in enumerate(raw_sections):
        if not isinstance(sec, dict):
            raise HTTPException(status_code=502, detail=f"大题第 {sidx + 1} 项格式错误")
        try:
            section_order = int(sec.get("section_order", sidx + 1))
        except (TypeError, ValueError):
            section_order = sidx + 1
        if section_order < 1 or section_order > 20:
            raise HTTPException(status_code=502, detail="大题序号无效")
        heading = str(sec.get("heading", "")).strip()
        if not heading:
            raise HTTPException(status_code=502, detail=f"大题 {section_order} 缺少 heading")
        if len(heading) > 256:
            raise HTTPException(status_code=502, detail=f"大题 {section_order} 标题过长")
        try:
            section_score = int(sec.get("section_score", 0))
        except (TypeError, ValueError) as e:
            raise HTTPException(status_code=502, detail=f"大题 {section_order} 分值无效") from e
        questions = sec.get("questions")
        if not isinstance(questions, list) or not questions:
            raise HTTPException(status_code=502, detail=f"大题 {section_order} 下缺少小题")
        if len(questions) > _MAX_MOCK_QUESTIONS:
            raise HTTPException(status_code=502, detail="单大题小题数量异常")

        sec_items: list[MockPaperItemOut] = []
        for qidx, q in enumerate(questions):
            short_h = heading if len(heading) <= 24 else heading[:24] + "…"
            label = f"大题「{short_h}」第 {qidx + 1} 小题"
            sec_items.append(_parse_one_question_dict(q, allowed_type_codes=allowed_type_codes, label=label))
        fixed: list[MockPaperItemOut] = []
        for j, it in enumerate(sec_items):
            if it.minor_index is None:
                fixed.append(it.model_copy(update={"minor_index": j + 1}))
            else:
                fixed.append(it)
        all_items.extend(fixed)
        sections.append(
            MockPaperSectionOut(
                section_order=section_order,
                heading=heading,
                section_score=max(0, min(200, section_score)),
                items=fixed,
            )
        )

    if len(all_items) > _MAX_MOCK_QUESTIONS:
        raise HTTPException(status_code=502, detail=f"题目数量超过上限（{_MAX_MOCK_QUESTIONS}）")
    nums = [it.number for it in all_items]
    if len(nums) != len(set(nums)):
        raise HTTPException(status_code=502, detail="题号存在重复")
    if sorted(nums) != list(range(1, len(nums) + 1)):
        raise HTTPException(status_code=502, detail="题号必须从 1 开始连续递增")

    ans_by_num = _answers_map_from_raw(obj.get("answers"))
    answers = _answers_list_for_items(all_items, ans_by_num)
    return sections, answers


def _parse_mock_paper_document(
    obj: dict,
    allowed_type_codes: set[str],
) -> tuple[list[MockPaperSectionOut], list[MockPaperAnswerOut]]:
    raw_sec = obj.get("sections")
    if isinstance(raw_sec, list) and len(raw_sec) > 0:
        sections, answers = _parse_mock_paper_sections(obj, allowed_type_codes)
    else:
        sections, answers = _parse_mock_paper_items(obj, allowed_type_codes)
    return _normalize_mock_paper_sections(sections), answers


@router.get("/mock-paper/question-types", response_model=list[MockPaperQuestionTypeItem])
async def list_mock_paper_question_types(
    grade_level_id: str = Query(..., min_length=1, max_length=64),
    subject_id: str = Query(..., min_length=1, max_length=64),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MockPaperQuestionTypeItem]:
    grade, subject = await _resolve_grade_subject(db, grade_level_id, subject_id)
    codes = question_type_codes_for(subject.code, grade.level)
    return [MockPaperQuestionTypeItem(code=c, name=question_type_label(c)) for c in codes]


@router.post("/mock-paper/generate", response_model=MockPaperGenerateResult)
async def generate_mock_paper(
    body: MockPaperGenerateBody,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MockPaperGenerateResult:
    ctx = await _mock_paper_load_context(db, body)
    ok, content, _ = await chat_completion(
        ctx.solve_base,
        ctx.solve_chat,
        ctx.solve_key,
        ctx.solve_model,
        ctx.messages,
        temperature=0.35,
        request_timeout=180.0,
    )
    if not ok or content is None:
        raise HTTPException(status_code=502, detail=content or "出题模型调用失败")
    return _mock_paper_build_result_from_content(content, ctx=ctx)


@router.post("/mock-paper/generate-stream")
async def generate_mock_paper_stream(
    body: MockPaperGenerateBody,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """模拟卷流式生成：NDJSON 行协议（phase / delta / done / error）。"""

    ctx = await _mock_paper_load_context(db, body)

    async def ndjson_gen():
        try:
            yield _ndline({"type": "phase", "label": "正在生成试卷…"})
            acc = ""
            async for delta in chat_completion_stream(
                ctx.solve_base,
                ctx.solve_chat,
                ctx.solve_key,
                ctx.solve_model,
                ctx.messages,
                temperature=0.35,
            ):
                acc += delta
                yield _ndline({"type": "delta", "text": delta})
            try:
                result = _mock_paper_build_result_from_content(acc, ctx=ctx)
            except HTTPException as e:
                yield _ndline({"type": "error", "message": _http_exc_detail(e)})
                return
            yield _ndline({"type": "done", "paper": result.model_dump()})
        except UpstreamChatError as e:
            yield _ndline({"type": "error", "message": e.message})
        except Exception as e:
            yield _ndline({"type": "error", "message": f"生成失败：{e}"})

    return StreamingResponse(ndjson_gen(), media_type="application/x-ndjson")
