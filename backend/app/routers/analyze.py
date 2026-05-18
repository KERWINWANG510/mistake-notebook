import base64
import json
import re
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.knowledge_tags import normalize_knowledge_tags
from app.models import AiProviderConfig, Subject, User
from app.routers.deps import get_current_user
from app.schemas import AnalyzeResult, OcrStemResult, SolveFromStemBody, SolveSuggestResult
from app.services.ai_client import UpstreamChatError, chat_completion, chat_completion_stream
from app.services.ai_config import get_active_ai_config
from app.services.crypto import decrypt_secret

router = APIRouter(prefix="/api/analyze", tags=["analyze"])

_OCR_SYSTEM_PROMPT = (
    "你是 OCR 助手。用户上传题目截图，请只识别题干文字（含公式则用 LaTeX 或不冲突的纯文本尽量表达）。"
    "若题目中部分文字带有印刷下划线（划重点、考点或填空横线等），请在 stem 中用 HTML 的 <u>…</u> 包裹对应文字，以便系统还原下划线效果；"
    "除 <u>…</u> 外不要输出其它 HTML 标签（禁止 script、style、a、img、iframe 等）。"
    "排版：大题说明、各小题、各选项之间用换行分隔；同一行写选项时 A. B. C. D. 之间至少两个空格，避免单词与 B.、C. 或下一题号粘连。"
    "题干也支持简单强调：需要分段时用空行分隔；需要加粗时用 **文字**。"
    "只输出一个 JSON 对象，不要 Markdown 代码块。字段仅包含：stem（字符串）。"
)

_STEM_LAYOUT_SYSTEM = (
    "你是题干排版助手，只根据已给出的 OCR 文本重新添加换行与空格，使网页展示时不断词、选项与题号不粘连。"
    "硬性规则：\n"
    "1. 不得改写、增删题目实质内容（单词、音标、数字、选项字母、句意一律保持）。\n"
    "2. 必须完整保留所有 <u>…</u> 标签及其中字符，不要改成别的标签。\n"
    "3. 若出现单词与选项标号粘连（如 enjoyment 与 B.、sure 与 C.、hair 与 B.、单词与下一题号如 car 与 3.），必须在粘连处插入换行，使标号单独起头或与前文明显分隔。\n"
    "4. 每个以「数字+英文点」或「罗马数字+点」等开头的小题（如 1.、2.、IV.）单独起行；其后 A. B. C. D. 建议每项单独一行，若同一行则 A.、B.、C.、D. 之间至少两个空格。\n"
    "5. 大题说明（如 I. Read and …）与第一小题之间可用一空行。\n"
    "6. 只输出整理后的题干全文，不要 JSON，不要用 Markdown 代码块，不要前后解释。"
)


def _build_ocr_user_payload(
    data_url: str,
    ocr_hint: str | None = None,
) -> list[dict[str, str | dict[str, str]]]:
    """识图用户消息：图片 + 可选的用户补充说明（重新识别时用于纠偏）。"""
    text_parts = ["请识别图片中的题目题干。"]
    hint = (ocr_hint or "").strip()
    if hint:
        text_parts.append(
            "用户补充说明（请结合图片核对并修正识别结果；若与图片明显冲突则以图片为准）：\n"
            + hint
        )
    return [
        {"type": "text", "text": "\n\n".join(text_parts)},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]


def _main_key(cfg: AiProviderConfig) -> str | None:
    return decrypt_secret(cfg.api_key_cipher)


def _vision_transport(cfg: AiProviderConfig) -> tuple[str, str, str | None]:
    if cfg.vision_base_url and cfg.vision_api_key_cipher:
        k = decrypt_secret(cfg.vision_api_key_cipher)
        return cfg.vision_base_url.rstrip("/"), cfg.chat_path, k
    return cfg.base_url, cfg.chat_path, _main_key(cfg)


def _solve_transport(cfg: AiProviderConfig) -> tuple[str, str, str | None]:
    if cfg.solve_base_url and cfg.solve_api_key_cipher:
        k = decrypt_secret(cfg.solve_api_key_cipher)
        return cfg.solve_base_url.rstrip("/"), cfg.chat_path, k
    return cfg.base_url, cfg.chat_path, _main_key(cfg)


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


async def _reformat_stem_layout(
    cfg: AiProviderConfig,
    stem_raw: str,
    *,
    model: str | None,
    model_solve: str | None,
) -> str:
    """识图后由文本模型整理换行与空格，减少选项粘连、误换行等问题。"""
    raw = (stem_raw or "").strip()
    if not raw:
        return raw
    s_base, s_chat, s_key = _solve_transport(cfg)
    if not s_key:
        return raw
    solve_model = model_solve or model or cfg.selected_model_solve or cfg.selected_model
    if not solve_model:
        return raw
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _STEM_LAYOUT_SYSTEM},
        {"role": "user", "content": f"下列为 OCR 题干，请按规则排版后仅输出正文：\n\n{raw}"},
    ]
    ok, content, _ = await chat_completion(
        s_base,
        s_chat,
        s_key,
        solve_model,
        messages,
        temperature=0.05,
    )
    if not ok or not content:
        return raw
    out = _strip_json_fence(content.strip())
    if not out.strip():
        return raw
    return out.strip()


def _parse_ocr_json(content: str) -> OcrStemResult:
    raw = _strip_json_fence(content)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"识图模型返回不是合法 JSON: {e}") from e
    try:
        return OcrStemResult.model_validate(obj)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"识图模型返回字段不符合约定: {e}") from e


def _parse_solve_json(content: str) -> SolveSuggestResult:
    raw = _strip_json_fence(content)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"解题模型返回不是合法 JSON: {e}") from e
    try:
        return SolveSuggestResult.model_validate(obj)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"解题模型返回字段不符合约定: {e}") from e


async def _subject_code_lines(db: AsyncSession) -> tuple[list[Subject], str]:
    sub_result = await db.execute(select(Subject).order_by(Subject.sort_order))
    subjects = sub_result.scalars().all()
    subject_lines = ", ".join(
        f"{s.code or s.id}:{s.name}" for s in subjects if s.code
    ) or ", ".join(f"{s.id}:{s.name}" for s in subjects)
    return subjects, subject_lines


def _ndline(obj: dict) -> bytes:
    return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")


def _normalize_solve_result(partial: SolveSuggestResult, subjects: list[Subject]) -> SolveSuggestResult:
    codes = {s.code for s in subjects if s.code}
    if partial.suggested_subject_code and codes and partial.suggested_subject_code not in codes:
        first = next((s.code for s in subjects if s.code), None)
        partial.suggested_subject_code = first
    if partial.suggested_grade_level is not None:
        lv = partial.suggested_grade_level
        if lv < 1 or lv > 12:
            partial.suggested_grade_level = None
    partial.knowledge_tags = normalize_knowledge_tags(partial.knowledge_tags)
    return partial


def _solve_system_prompt(subject_lines: str, *, subject_hint: str | None = None, grade_hint: str | None = None) -> str:
    context = ""
    if subject_hint or grade_hint:
        parts = []
        if subject_hint:
            parts.append(f"科目：{subject_hint}")
        if grade_hint:
            parts.append(f"年级：{grade_hint}")
        context = "已知" + "，".join(parts) + "。知识点标签须符合该年级该科目的教学范围。"
    return (
        "你是中小学错题辅导助手。下面给出某道题的题干文字。"
        "题干中若出现 <u>…</u>，表示原题中该段文字带印刷下划线（划重点或考点），请在理解与作答时予以重视。"
        "请给出简明、可跟做的解题思路与最终答案，便于学生复习错题；避免冗长铺垫与重复解释。"
        "analysis 字段要求：使用简洁 Markdown 排版（保存为纯文本）："
        "（1）按关键步骤编号，一般 3～5 步即可，简单题可更少，复杂题不超过 7 步；"
        "（2）每步一行标题用 **加粗**（如 **1. 列式：**），下面用 1～2 句写清本步做法与结果，不必逐步解释「为什么」；"
        "（3）步骤之间空一行；必要时可用「- 」列要点，但不要堆砌；"
        "（4）仅在有明显价值时简短补充 **【易错点】** 或 **【知识点】**（各不超过 2 句）；"
        "（5）若有多问，用 **【第 1 问】** 等分段，每问仍保持精简。"
        "answer 字段写最终结论（含单位），与 analysis 一致。"
        "同时推断科目与年级：科目使用下列编码之一（优先精确匹配）："
        f"{subject_lines}。"
        "年级用 1-12 的整数表示：1-9 为一至九年级，10-12 为高一至高三。"
        "knowledge_tags 为字符串数组，给出 1～3 个本题涉及的知识点标签："
        "须结合推断出的年级与科目，使用简短中文名词短语（如「一元一次方程」「完形填空」「牛顿第二定律」），"
        "不要写过于宽泛的词（如「数学」「基础」）。"
        "标签口径须统一：优先采用教材单元级、略上位的名称，同一数组内禁止同时出现上位概念与其下位细目"
        "（错误：同时写「小数四则运算」与「小数除法」；正确：只写「小数四则运算」）。"
        "具体运算子类型（加、减、乘、除及混合）应归入对应的「××四则运算」或同级上位标签，勿再单列子技能。"
        "各标签之间语义勿重叠，宁可少而精，每个标签应能独立代表本题考查范围。"
        f"{context}"
        "只输出一个 JSON 对象，不要 Markdown 代码块，不要 JSON 以外的说明。字段为："
        "analysis（解题思路，纯文本，可用换行与 **加粗**）, answer（最终答案）, "
        "suggested_subject_code（科目编码，必须与列表之一一致，若无法判断则填第一个编码）, "
        "suggested_grade_level（整数 1-12）, knowledge_tags（字符串数组）。不要重复输出 stem 字段。"
    )


async def _build_solve_messages(
    db: AsyncSession,
    stem_text: str,
    *,
    subject_code: str | None = None,
    grade_level: int | None = None,
) -> tuple[list[Subject], list[dict[str, Any]]]:
    """构造解题对话 messages；返回 subjects 与 messages。"""
    subjects, subject_lines = await _subject_code_lines(db)
    subject_hint: str | None = None
    if subject_code:
        subj = next((s for s in subjects if s.code == subject_code), None)
        subject_hint = subj.name if subj else subject_code
    grade_hint: str | None = None
    if grade_level is not None:
        if 1 <= grade_level <= 9:
            grade_hint = f"{grade_level}年级"
        elif grade_level == 10:
            grade_hint = "高一"
        elif grade_level == 11:
            grade_hint = "高二"
        elif grade_level == 12:
            grade_hint = "高三"
    solve_messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": _solve_system_prompt(subject_lines, subject_hint=subject_hint, grade_hint=grade_hint),
        },
        {"role": "user", "content": f"题干如下：\n{stem_text}"},
    ]
    return subjects, solve_messages


async def _solve_from_stem_text(
    db: AsyncSession,
    cfg: AiProviderConfig,
    stem_text: str,
    *,
    model: str | None = None,
    model_solve: str | None = None,
    subject_code: str | None = None,
    grade_level: int | None = None,
) -> SolveSuggestResult:
    s_base, s_chat, s_key = _solve_transport(cfg)
    if not s_key:
        raise HTTPException(status_code=409, detail="解题步骤缺少可用的 API Key（请配置主接入密钥或解题独立密钥）")

    solve_model = model_solve or model or cfg.selected_model_solve or cfg.selected_model
    if not solve_model:
        raise HTTPException(
            status_code=400,
            detail="请配置默认模型，或配置解题模型，或通过参数传入",
        )

    subjects, solve_messages = await _build_solve_messages(
        db, stem_text, subject_code=subject_code, grade_level=grade_level
    )

    ok, solve_content, _ = await chat_completion(
        s_base,
        s_chat,
        s_key,
        solve_model,
        solve_messages,
        temperature=0.2,
    )
    if not ok or solve_content is None:
        raise HTTPException(status_code=502, detail=solve_content or "解题模型调用失败")

    partial = _parse_solve_json(solve_content)
    return _normalize_solve_result(partial, subjects)


@router.post("/solve-stem", response_model=SolveSuggestResult)
async def solve_from_stem(
    body: SolveFromStemBody,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    model: str | None = Query(None, description="覆盖默认模型（解题）"),
    model_solve: str | None = Query(None, description="覆盖解题与分类模型"),
) -> SolveSuggestResult:
    cfg = await get_active_ai_config(db, _user)

    stem_text = body.stem.strip()
    if not stem_text:
        raise HTTPException(status_code=400, detail="题干不能为空")
    return await _solve_from_stem_text(
        db,
        cfg,
        stem_text,
        model=model,
        model_solve=model_solve,
        subject_code=body.subject_code,
        grade_level=body.grade_level,
    )


def _http_exc_detail(exc: HTTPException) -> str:
    d = exc.detail
    return d if isinstance(d, str) else str(d)


@router.post("/stream")
async def analyze_image_stream(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    ocr_hint: str | None = Form(None, description="识图补充说明（重新识别时用户纠偏）"),
    model: str | None = Query(None, description="覆盖默认模型（同时用于识图与解题）"),
    model_vision: str | None = Query(None, description="覆盖识图/OCR 模型"),
    model_solve: str | None = Query(None, description="覆盖解题与分类模型"),
) -> StreamingResponse:
    """流式识别错题：NDJSON 行协议，便于前端实时展示上游输出。"""
    cfg = await get_active_ai_config(db, _user)

    v_base, v_chat, v_key = _vision_transport(cfg)
    if not v_key:
        raise HTTPException(status_code=409, detail="识图步骤缺少可用的 API Key（请配置主接入密钥或识图独立密钥）")

    vision_model = model_vision or model or cfg.selected_model_vision or cfg.selected_model
    solve_model = model_solve or model or cfg.selected_model_solve or cfg.selected_model
    if not vision_model or not solve_model:
        raise HTTPException(
            status_code=400,
            detail="请配置默认模型，或分别配置识图模型与解题模型，或通过参数传入",
        )

    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片过大，请压缩后重试（最大约 15MB）")

    ctype = file.content_type or "image/jpeg"
    if not ctype.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")

    b64 = base64.standard_b64encode(data).decode("ascii")
    data_url = f"data:{ctype};base64,{b64}"

    ocr_user = _build_ocr_user_payload(data_url, ocr_hint)
    ocr_messages: list[dict[str, Any]] = [
        {"role": "system", "content": _OCR_SYSTEM_PROMPT},
        {"role": "user", "content": ocr_user},
    ]

    async def ndjson_gen():
        try:
            yield _ndline({"type": "phase", "phase": "ocr", "label": "正在识图…"})
            ocr_acc = ""
            async for delta in chat_completion_stream(
                v_base,
                v_chat,
                v_key,
                vision_model,
                ocr_messages,
                temperature=0.1,
            ):
                ocr_acc += delta
                yield _ndline({"type": "delta", "phase": "ocr", "text": delta})
            try:
                ocr = _parse_ocr_json(ocr_acc)
            except HTTPException as e:
                yield _ndline({"type": "error", "message": _http_exc_detail(e)})
                return
            stem_text = ocr.stem.strip()
            if not stem_text:
                yield _ndline({"type": "error", "message": "识图结果为空，请更换识图模型或重试"})
                return
            yield _ndline({"type": "phase", "phase": "layout", "label": "正在优化题干排版…"})
            stem_text = await _reformat_stem_layout(
                cfg, stem_text, model=model, model_solve=model_solve
            )
            yield _ndline({"type": "stem", "text": stem_text})

            s_base, s_chat, s_key = _solve_transport(cfg)
            if not s_key:
                yield _ndline(
                    {"type": "error", "message": "解题步骤缺少可用的 API Key（请配置主接入密钥或解题独立密钥）"},
                )
                return

            subjects, solve_messages = await _build_solve_messages(db, stem_text)

            yield _ndline({"type": "phase", "phase": "solve", "label": "正在生成解析与答案…"})
            sol_acc = ""
            async for delta in chat_completion_stream(
                s_base,
                s_chat,
                s_key,
                solve_model,
                solve_messages,
                temperature=0.2,
            ):
                sol_acc += delta
                yield _ndline({"type": "delta", "phase": "solve", "text": delta})
            try:
                partial = _parse_solve_json(sol_acc)
            except HTTPException as e:
                yield _ndline({"type": "error", "message": _http_exc_detail(e)})
                return
            partial = _normalize_solve_result(partial, subjects)
            yield _ndline(
                {
                    "type": "done",
                    "stem": stem_text,
                    "analysis": partial.analysis,
                    "answer": partial.answer,
                    "suggested_subject_code": partial.suggested_subject_code,
                    "suggested_grade_level": partial.suggested_grade_level,
                    "knowledge_tags": partial.knowledge_tags,
                },
            )
        except UpstreamChatError as e:
            yield _ndline({"type": "error", "message": e.message})
        except Exception as e:
            yield _ndline({"type": "error", "message": f"识别过程出错：{e}"})

    return StreamingResponse(
        ndjson_gen(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("", response_model=AnalyzeResult)
async def analyze_image(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    ocr_hint: str | None = Form(None, description="识图补充说明（重新识别时用户纠偏）"),
    model: str | None = Query(None, description="覆盖默认模型（同时用于识图与解题）"),
    model_vision: str | None = Query(None, description="覆盖识图/OCR 模型"),
    model_solve: str | None = Query(None, description="覆盖解题与分类模型"),
) -> AnalyzeResult:
    cfg = await get_active_ai_config(db, _user)

    v_base, v_chat, v_key = _vision_transport(cfg)
    if not v_key:
        raise HTTPException(status_code=409, detail="识图步骤缺少可用的 API Key（请配置主接入密钥或识图独立密钥）")

    vision_model = model_vision or model or cfg.selected_model_vision or cfg.selected_model
    solve_model = model_solve or model or cfg.selected_model_solve or cfg.selected_model
    if not vision_model or not solve_model:
        raise HTTPException(
            status_code=400,
            detail="请配置默认模型，或分别配置识图模型与解题模型，或通过参数传入",
        )

    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片过大，请压缩后重试（最大约 15MB）")

    ctype = file.content_type or "image/jpeg"
    if not ctype.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")

    b64 = base64.standard_b64encode(data).decode("ascii")
    data_url = f"data:{ctype};base64,{b64}"

    ocr_user = _build_ocr_user_payload(data_url, ocr_hint)
    ocr_messages = [
        {"role": "system", "content": _OCR_SYSTEM_PROMPT},
        {"role": "user", "content": ocr_user},
    ]

    ok1, ocr_content, _ = await chat_completion(
        v_base,
        v_chat,
        v_key,
        vision_model,
        ocr_messages,
        temperature=0.1,
    )
    if not ok1 or ocr_content is None:
        raise HTTPException(status_code=502, detail=ocr_content or "识图模型调用失败")

    ocr = _parse_ocr_json(ocr_content)
    stem_text = ocr.stem.strip()
    if not stem_text:
        raise HTTPException(status_code=502, detail="识图结果为空，请更换识图模型或重试")

    stem_text = await _reformat_stem_layout(cfg, stem_text, model=model, model_solve=model_solve)

    partial = await _solve_from_stem_text(
        db, cfg, stem_text, model=model, model_solve=model_solve
    )
    return AnalyzeResult(
        stem=stem_text,
        analysis=partial.analysis,
        answer=partial.answer,
        suggested_subject_code=partial.suggested_subject_code,
        suggested_grade_level=partial.suggested_grade_level,
        knowledge_tags=partial.knowledge_tags,
    )
