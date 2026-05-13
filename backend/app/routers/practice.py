import base64
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models import AiProviderConfig, Mistake, User
from app.routers.analyze import _solve_transport, _strip_json_fence, _vision_transport
from app.routers.deps import get_current_user
from app.routers.mistakes import _require_owner
from app.schemas import PracticeCheckResult, PracticeDifficulty, PracticeGenerateBody, PracticeGenerateResult
from app.services.ai_client import chat_completion

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
