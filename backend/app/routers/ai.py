from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AiProviderConfig, AiProviderPreset, User
from app.routers.deps import get_current_user
from app.schemas import (
    AiConfigCreate,
    AiConfigOut,
    AiConfigUpdate,
    AiPresetOut,
    ListModelsPreviewBody,
    ListModelsResponse,
)
from app.services.ai_client import fetch_models
from app.services.crypto import decrypt_secret, encrypt_secret

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _config_out(row: AiProviderConfig) -> AiConfigOut:
    return AiConfigOut(
        id=row.id,
        user_label=row.user_label,
        preset_id=row.preset_id,
        base_url=row.base_url,
        models_path=row.models_path,
        chat_path=row.chat_path,
        selected_model=row.selected_model,
        selected_model_vision=row.selected_model_vision,
        selected_model_solve=row.selected_model_solve,
        vision_preset_id=row.vision_preset_id,
        vision_base_url=row.vision_base_url,
        has_vision_api_key=bool(row.vision_api_key_cipher),
        solve_preset_id=row.solve_preset_id,
        solve_base_url=row.solve_base_url,
        has_solve_api_key=bool(row.solve_api_key_cipher),
        is_active=row.is_active,
        has_api_key=bool(row.api_key_cipher),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/presets", response_model=list[AiPresetOut])
async def list_presets(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AiPresetOut]:
    result = await db.execute(select(AiProviderPreset).order_by(AiProviderPreset.sort_order))
    rows = result.scalars().all()
    return [AiPresetOut.model_validate(r) for r in rows]


@router.get("/configs", response_model=list[AiConfigOut])
async def list_configs(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AiConfigOut]:
    result = await db.execute(select(AiProviderConfig).order_by(AiProviderConfig.created_at.desc()))
    rows = result.scalars().all()
    return [_config_out(r) for r in rows]


@router.post("/configs", response_model=AiConfigOut)
async def create_config(
    body: AiConfigCreate,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiConfigOut:
    if body.preset_id:
        pr = await db.get(AiProviderPreset, body.preset_id)
        if not pr:
            raise HTTPException(status_code=400, detail="无效的 preset_id")
    vb = (body.vision_base_url or "").strip().rstrip("/") or None
    vk = (body.vision_api_key or "").strip()
    if vb and not vk:
        raise HTTPException(status_code=400, detail="已填写识图独立 Base URL 时，请同时填写识图 API Key")
    if vk and not vb:
        raise HTTPException(status_code=400, detail="已填写识图 API Key 时，请同时填写识图独立 Base URL")
    if body.vision_preset_id:
        pr = await db.get(AiProviderPreset, body.vision_preset_id)
        if not pr:
            raise HTTPException(status_code=400, detail="无效的识图 preset_id")
    sb = (body.solve_base_url or "").strip().rstrip("/") or None
    sk = (body.solve_api_key or "").strip()
    if sb and not sk:
        raise HTTPException(status_code=400, detail="已填写解题独立 Base URL 时，请同时填写解题 API Key")
    if sk and not sb:
        raise HTTPException(status_code=400, detail="已填写解题 API Key 时，请同时填写解题独立 Base URL")
    if body.solve_preset_id:
        pr = await db.get(AiProviderPreset, body.solve_preset_id)
        if not pr:
            raise HTTPException(status_code=400, detail="无效的解题 preset_id")
    row = AiProviderConfig(
        user_label=body.user_label,
        preset_id=body.preset_id,
        base_url=body.base_url.rstrip("/"),
        models_path=body.models_path,
        chat_path=body.chat_path,
        api_key_cipher=encrypt_secret(body.api_key) if body.api_key else None,
        selected_model=body.selected_model,
        selected_model_vision=body.selected_model_vision,
        selected_model_solve=body.selected_model_solve,
        vision_preset_id=body.vision_preset_id,
        vision_base_url=vb,
        vision_api_key_cipher=encrypt_secret(body.vision_api_key) if vk else None,
        solve_preset_id=body.solve_preset_id,
        solve_base_url=sb,
        solve_api_key_cipher=encrypt_secret(body.solve_api_key) if sk else None,
        is_active=False,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    total = await db.scalar(select(func.count()).select_from(AiProviderConfig))
    if total == 1:
        res_all = await db.execute(select(AiProviderConfig))
        for c in res_all.scalars().all():
            c.is_active = False
        row.is_active = True
        await db.commit()
        await db.refresh(row)
    return _config_out(row)


@router.patch("/configs/{config_id}", response_model=AiConfigOut)
async def update_config(
    config_id: str,
    body: AiConfigUpdate,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiConfigOut:
    row = await db.get(AiProviderConfig, config_id)
    if not row:
        raise HTTPException(status_code=404, detail="配置不存在")
    if body.user_label is not None:
        row.user_label = body.user_label
    if body.base_url is not None:
        row.base_url = body.base_url.rstrip("/")
    if body.models_path is not None:
        row.models_path = body.models_path
    if body.chat_path is not None:
        row.chat_path = body.chat_path
    if body.api_key is not None and body.api_key != "":
        row.api_key_cipher = encrypt_secret(body.api_key)
    if body.selected_model is not None:
        row.selected_model = body.selected_model or None
    if body.selected_model_vision is not None:
        row.selected_model_vision = body.selected_model_vision or None
    if body.selected_model_solve is not None:
        row.selected_model_solve = body.selected_model_solve or None

    data = body.model_dump(exclude_unset=True)
    if "vision_base_url" in data:
        vb_raw = data["vision_base_url"]
        if vb_raw is None or (isinstance(vb_raw, str) and not vb_raw.strip()):
            row.vision_base_url = None
            row.vision_api_key_cipher = None
            row.vision_preset_id = None
        else:
            row.vision_base_url = str(vb_raw).strip().rstrip("/")
    if "vision_preset_id" in data:
        row.vision_preset_id = data["vision_preset_id"] or None
    if "vision_api_key" in data and data["vision_api_key"]:
        row.vision_api_key_cipher = encrypt_secret(data["vision_api_key"])

    if "solve_base_url" in data:
        sb_raw = data["solve_base_url"]
        if sb_raw is None or (isinstance(sb_raw, str) and not sb_raw.strip()):
            row.solve_base_url = None
            row.solve_api_key_cipher = None
            row.solve_preset_id = None
        else:
            row.solve_base_url = str(sb_raw).strip().rstrip("/")
    if "solve_preset_id" in data:
        row.solve_preset_id = data["solve_preset_id"] or None
    if "solve_api_key" in data and data["solve_api_key"]:
        row.solve_api_key_cipher = encrypt_secret(data["solve_api_key"])

    await db.commit()
    await db.refresh(row)
    return _config_out(row)


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: str,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    row = await db.get(AiProviderConfig, config_id)
    if not row:
        raise HTTPException(status_code=404, detail="配置不存在")
    if row.is_active:
        raise HTTPException(status_code=400, detail="请先取消激活或激活其他配置后再删除")
    await db.delete(row)
    await db.commit()
    return {"status": "ok"}


@router.post("/configs/{config_id}/activate", response_model=AiConfigOut)
async def activate_config(
    config_id: str,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiConfigOut:
    row = await db.get(AiProviderConfig, config_id)
    if not row:
        raise HTTPException(status_code=404, detail="配置不存在")
    result = await db.execute(select(AiProviderConfig))
    for c in result.scalars().all():
        c.is_active = False
    row.is_active = True
    await db.commit()
    await db.refresh(row)
    return _config_out(row)


@router.post("/list-models-preview", response_model=ListModelsResponse)
async def list_models_preview(
    body: ListModelsPreviewBody,
    _: User = Depends(get_current_user),
) -> ListModelsResponse:
    """使用当前表单中的 Base URL、路径与 API Key 拉取模型列表，无需先保存配置。"""
    base = body.base_url.rstrip("/")
    path = body.models_path.strip() or "/models"
    return await fetch_models(base, path, body.api_key.strip())


@router.post("/configs/{config_id}/list-models", response_model=ListModelsResponse)
async def list_models(
    config_id: str,
    target: Literal["main", "vision", "solve"] = Query("main", description="main=主接入；vision/solve=独立接入"),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ListModelsResponse:
    row = await db.get(AiProviderConfig, config_id)
    if not row:
        raise HTTPException(status_code=404, detail="配置不存在")
    if target == "main":
        key = decrypt_secret(row.api_key_cipher)
        return await fetch_models(row.base_url, row.models_path, key)
    if target == "vision":
        if not row.vision_base_url or not row.vision_api_key_cipher:
            raise HTTPException(status_code=400, detail="未配置识图独立服务商")
        key = decrypt_secret(row.vision_api_key_cipher)
        return await fetch_models(row.vision_base_url.rstrip("/"), row.models_path, key)
    if not row.solve_base_url or not row.solve_api_key_cipher:
        raise HTTPException(status_code=400, detail="未配置解题独立服务商")
    key = decrypt_secret(row.solve_api_key_cipher)
    return await fetch_models(row.solve_base_url.rstrip("/"), row.models_path, key)
