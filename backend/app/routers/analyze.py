import base64
import json
import re

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AiProviderConfig, Subject, User
from app.routers.deps import get_current_user
from app.schemas import AnalyzeResult, OcrStemResult, SolveFromStemBody, SolveSuggestResult
from app.services.ai_client import chat_completion
from app.services.crypto import decrypt_secret

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


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


def _normalize_solve_result(partial: SolveSuggestResult, subjects: list[Subject]) -> SolveSuggestResult:
    codes = {s.code for s in subjects if s.code}
    if partial.suggested_subject_code and codes and partial.suggested_subject_code not in codes:
        first = next((s.code for s in subjects if s.code), None)
        partial.suggested_subject_code = first
    if partial.suggested_grade_level is not None:
        lv = partial.suggested_grade_level
        if lv < 1 or lv > 12:
            partial.suggested_grade_level = None
    return partial


def _solve_system_prompt(subject_lines: str) -> str:
    return (
        "你是中小学错题辅导助手。下面给出某道题的题干文字。"
        "请给出尽可能详细、可跟做的解题过程与最终答案，便于学生复习错题。"
        "analysis 字段要求：使用简洁 Markdown 排版（保存为纯文本）："
        "（1）每个大步骤之间空一行；步骤行首用「1. 」「2. 」编号，步骤标题用 **加粗**（如 **1. 审题：**）；"
        "（2）步骤内分点可用「- 」列表；知识点、易错点等小节用 **【知识点】** **【易错点】** 等加粗标签起头；"
        "（3）每一步说明「做什么、为什么、得到什么」；"
        "（4）若有多问，用 **【第 1 问】** 等分段；"
        "（5）篇幅宜详不宜略，一般不少于 4 步，复杂题可更长。"
        "answer 字段写最终结论（含单位），与 analysis 一致。"
        "同时推断科目与年级：科目使用下列编码之一（优先精确匹配）："
        f"{subject_lines}。"
        "年级用 1-12 的整数表示：1-9 为一至九年级，10-12 为高一至高三。"
        "只输出一个 JSON 对象，不要 Markdown 代码块，不要 JSON 以外的说明。字段为："
        "analysis（解题思路，纯文本，可用换行与 **加粗**）, answer（最终答案）, "
        "suggested_subject_code（科目编码，必须与列表之一一致，若无法判断则填第一个编码）, "
        "suggested_grade_level（整数 1-12）。不要重复输出 stem 字段。"
    )


async def _solve_from_stem_text(
    db: AsyncSession,
    cfg: AiProviderConfig,
    stem_text: str,
    *,
    model: str | None = None,
    model_solve: str | None = None,
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

    subjects, subject_lines = await _subject_code_lines(db)
    solve_messages = [
        {"role": "system", "content": _solve_system_prompt(subject_lines)},
        {"role": "user", "content": f"题干如下：\n{stem_text}"},
    ]

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
    r = await db.execute(select(AiProviderConfig).where(AiProviderConfig.is_active.is_(True)))
    cfg = r.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=409, detail="未配置或未激活 AI，请先在设置中完成配置")

    stem_text = body.stem.strip()
    if not stem_text:
        raise HTTPException(status_code=400, detail="题干不能为空")
    return await _solve_from_stem_text(db, cfg, stem_text, model=model, model_solve=model_solve)


@router.post("", response_model=AnalyzeResult)
async def analyze_image(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    model: str | None = Query(None, description="覆盖默认模型（同时用于识图与解题）"),
    model_vision: str | None = Query(None, description="覆盖识图/OCR 模型"),
    model_solve: str | None = Query(None, description="覆盖解题与分类模型"),
) -> AnalyzeResult:
    r = await db.execute(select(AiProviderConfig).where(AiProviderConfig.is_active.is_(True)))
    cfg = r.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=409, detail="未配置或未激活 AI，请先在设置中完成配置")

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

    ocr_system = (
        "你是 OCR 助手。用户上传题目截图，请只识别题干文字（含公式则用 LaTeX 或纯文本尽量表达）。"
        "只输出一个 JSON 对象，不要 Markdown。字段仅包含：stem（字符串）。"
    )
    ocr_user: list[dict] = [
        {"type": "text", "text": "请识别图片中的题目题干。"},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]
    ocr_messages = [
        {"role": "system", "content": ocr_system},
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

    partial = await _solve_from_stem_text(
        db, cfg, stem_text, model=model, model_solve=model_solve
    )
    return AnalyzeResult(
        stem=stem_text,
        analysis=partial.analysis,
        answer=partial.answer,
        suggested_subject_code=partial.suggested_subject_code,
        suggested_grade_level=partial.suggested_grade_level,
    )
