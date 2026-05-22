"""识图 / 视觉多模态请求：消息体构建与图片校验。"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

# 百炼 data-uri 单条上限约 10MB；留余量避免 base64 膨胀后超限
VISION_MAX_IMAGE_BYTES = 7 * 1024 * 1024
VISION_MAX_DATA_URL_CHARS = 10 * 1024 * 1024


def sniff_image_media_type(data: bytes, fallback: str | None = None) -> str:
    """根据文件头推断图片 MIME，避免反代将 content-type 标成 octet-stream。"""
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(data) >= 6 and data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    fb = (fallback or "").split(";")[0].strip().lower()
    if fb.startswith("image/"):
        return fb
    return "image/jpeg"


def ensure_image_upload_limits(data: bytes, data_url: str) -> None:
    if len(data) > VISION_MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="图片过大，请压缩后重试（建议单张不超过约 7MB）",
        )
    if len(data_url) > VISION_MAX_DATA_URL_CHARS:
        raise HTTPException(
            status_code=400,
            detail="图片编码后超过上游限制，请压缩或换一张较小的图片后重试",
        )


_VISION_CAPABLE_HINTS = (
    "-vl",
    "vl-",
    "/vl",
    "vision",
    "ocr",
    "qwen-vl",
    "qvq",
    "glm-4v",
    "gpt-4o",
    "gpt-4.1",
    "gpt-4-vision",
    "kimi-k2",
    "qwen3.6",
    "qwen3.5",
    "qwen3-vl",
    "qwen2.5-vl",
    "qwen2-vl",
)

_TEXT_ONLY_PREFIXES = (
    "qwen-turbo",
    "qwen-plus",
    "qwen-max",
    "qwen-long",
    "deepseek-chat",
    "deepseek-coder",
    "deepseek-reasoner",
    "moonshot-v1",
    "gpt-3.5",
)


def _has_vision_name_hint(m: str) -> bool:
    if "kimi" in m and any(h in m for h in ("k2", "2.5", "2.6", "k2.5")):
        return True
    return any(h in m for h in _VISION_CAPABLE_HINTS)


def is_known_text_only_model(model: str) -> bool:
    """明显不支持图像输入的模型（用于提前给出可读错误）。"""
    m = (model or "").strip().lower()
    if not m or _has_vision_name_hint(m):
        return False
    return any(m == p or m.startswith(p + "-") or m.startswith(p + ".") for p in _TEXT_ONLY_PREFIXES)


def is_likely_vision_capable_model(model: str) -> bool:
    """根据模型 id 常见命名判断是否具备视觉/OCR 能力。"""
    m = (model or "").strip().lower()
    if not m or is_known_text_only_model(m):
        return False
    return _has_vision_name_hint(m)


def effective_vision_model(
    selected_model_vision: str | None,
    selected_model: str | None,
) -> str | None:
    v = (selected_model_vision or "").strip()
    if v:
        return v
    d = (selected_model or "").strip()
    return d or None


def vision_model_ocr_error(model: str | None) -> str | None:
    """识图模型不可用时返回错误说明，可用则返回 None。"""
    m = (model or "").strip()
    if not m:
        return None
    if is_known_text_only_model(m):
        return (
            f"模型「{m}」为纯文本模型，不支持图片/OCR 识图。"
            "请选择视觉模型（如 qwen-vl-plus、qwen-vl-ocr-latest、qwen3.6-plus、kimi-k2.5 等）"
        )
    return None


def vision_model_ocr_warning(model: str | None) -> str | None:
    """模型能力不明确时返回提示（不阻止保存）。"""
    m = (model or "").strip()
    if not m or vision_model_ocr_error(m):
        return None
    if is_likely_vision_capable_model(m):
        return None
    return f"模型「{m}」可能不支持图片识图，若识别失败请改用 qwen-vl-* 或 qwen3.6-plus 等视觉模型"


def assert_vision_capable_model(model: str) -> None:
    err = vision_model_ocr_error(model)
    if err:
        raise HTTPException(status_code=400, detail=err)


def assert_vision_selection(
    *,
    selected_model_vision: str | None,
    selected_model: str | None,
) -> None:
    """校验错题识图将使用的有效模型（识图专用或回退到默认模型）。"""
    effective = effective_vision_model(selected_model_vision, selected_model)
    if not effective:
        return
    assert_vision_capable_model(effective)


def build_vision_user_messages(
    *,
    system_prompt: str,
    task_text: str,
    data_url: str,
    extra_text: str | None = None,
) -> list[dict[str, Any]]:
    """构建 OpenAI 兼容多模态消息：单条 user，system 并入文本，避免部分上游拒绝 system+图混排。"""
    text_parts = [system_prompt.strip(), "", task_text.strip()]
    if extra_text and extra_text.strip():
        text_parts.extend(["", extra_text.strip()])
    return [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": "\n\n".join(text_parts)},
            ],
        }
    ]
