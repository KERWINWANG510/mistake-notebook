"""调用 OpenAI 兼容接口：模型列表与对话。"""

from typing import Any

import httpx

from app.schemas import ListModelsResponse, ModelItem


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
) -> tuple[bool, str | None, dict[str, Any] | None]:
    url = join_url(base_url, chat_path)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
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
