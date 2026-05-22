"""调用 OpenAI 兼容接口：模型列表与对话。"""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.schemas import ListModelsResponse, ModelItem


def effective_chat_temperature(model: str, requested: float) -> float:
    """部分上游（如 Moonshot Kimi K2 / 2.6）仅允许 temperature=1，否则会返回 400。

    与 OpenAI 兼容网关约定：模型 id 常为 kimi-k2-* 或含 kimi 与 k2 / 2.6 等字样。
    """
    m = (model or "").strip().lower()
    if not m:
        return requested
    if "kimi-k2" in m:
        return 1.0
    if "kimi" in m and ("k2" in m or "2.6" in m):
        return 1.0
    if "moonshot" in m and "k2" in m:
        return 1.0
    return requested


def join_url(base_url: str, path: str) -> str:
    b = base_url.rstrip("/")
    p = path if path.startswith("/") else f"/{path}"
    return f"{b}{p}"


async def fetch_models(base_url: str, models_path: str, api_key: str | None) -> ListModelsResponse:
    url = join_url(base_url, models_path)
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(url, headers=headers)
    except httpx.TimeoutException:
        return ListModelsResponse(ok=False, error_code="UPSTREAM_TIMEOUT", message="请求上游超时")
    except httpx.RequestError as e:
        return ListModelsResponse(ok=False, error_code="UPSTREAM_NETWORK", message=str(e))

    if r.status_code == 401:
        return ListModelsResponse(ok=False, error_code="UPSTREAM_401", message="API Key 无效或未授权")
    if r.status_code != 200:
        return ListModelsResponse(
            ok=False,
            error_code="UPSTREAM_HTTP",
            message=f"上游返回 {r.status_code}",
        )
    try:
        data = r.json()
    except Exception:
        return ListModelsResponse(ok=False, error_code="UNSUPPORTED_FORMAT", message="响应不是合法 JSON")

    models: list[ModelItem] = []
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        for item in data["data"]:
            if isinstance(item, dict) and "id" in item:
                mid = str(item["id"])
                models.append(ModelItem(id=mid, raw=item))
    elif isinstance(data, dict) and "models" in data:
        inner = data["models"]
        if isinstance(inner, list):
            for item in inner:
                if isinstance(item, dict) and "name" in item:
                    models.append(ModelItem(id=str(item["name"]), raw=item))
                elif isinstance(item, str):
                    models.append(ModelItem(id=item))

    return ListModelsResponse(ok=True, models=models)


async def chat_completion(
    base_url: str,
    chat_path: str,
    api_key: str | None,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.2,
    *,
    request_timeout: float = 120.0,
    response_format: dict[str, Any] | None = None,
) -> tuple[bool, str | None, dict[str, Any] | None]:
    url = join_url(base_url, chat_path)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": effective_chat_temperature(model, temperature),
    }
    if response_format is not None:
        payload["response_format"] = response_format
    try:
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            r = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException:
        return False, "上游对话请求超时", None
    except httpx.RequestError as e:
        return False, str(e), None

    if r.status_code != 200:
        try:
            detail = r.json()
        except Exception:
            detail = {"text": r.text[:500]}
        return False, f"上游错误 {r.status_code}: {detail}", None

    try:
        body = r.json()
    except Exception:
        return False, "无法解析上游 JSON", None

    choices = body.get("choices")
    if not choices or not isinstance(choices, list):
        return False, "响应缺少 choices", None
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if not isinstance(content, str):
        return False, "响应内容格式异常", None
    return True, content, body


class UpstreamChatError(Exception):
    """上游对话接口返回错误（非 200 或无法解析流）。"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


async def chat_completion_stream(
    base_url: str,
    chat_path: str,
    api_key: str | None,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.2,
    *,
    response_format: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    """调用上游 chat.completions 流式接口，逐段产出文本 delta（不含 JSON 封装）。"""
    url = join_url(base_url, chat_path)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": effective_chat_temperature(model, temperature),
        "stream": True,
    }
    if response_format is not None:
        payload["response_format"] = response_format
    timeout = httpx.Timeout(180.0, connect=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as r:
            if r.status_code != 200:
                err_body = (await r.aread()).decode("utf-8", errors="replace")[:4000]
                raise UpstreamChatError(f"上游错误 {r.status_code}: {err_body}")

            async for line in r.aiter_lines():
                if line is None:
                    continue
                s = line.strip()
                if not s:
                    continue
                if not s.startswith("data:"):
                    continue
                payload_str = s[5:].lstrip()
                if payload_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload_str)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices")
                if not choices or not isinstance(choices, list):
                    continue
                first = choices[0] if choices else None
                if not isinstance(first, dict):
                    continue
                delta = first.get("delta")
                if not isinstance(delta, dict):
                    continue
                content = delta.get("content")
                if isinstance(content, str) and content:
                    yield content
