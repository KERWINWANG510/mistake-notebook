"""当前用户的 AI 接入配置查询与校验。"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AiProviderConfig, User


def require_user_ai_config(row: AiProviderConfig | None, user: User) -> AiProviderConfig:
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="配置不存在")
    return row


async def get_active_ai_config(db: AsyncSession, user: User) -> AiProviderConfig:
    r = await db.execute(
        select(AiProviderConfig).where(
            AiProviderConfig.user_id == user.id,
            AiProviderConfig.is_active.is_(True),
        )
    )
    cfg = r.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=409, detail="未配置或未激活 AI，请先在设置中完成配置")
    return cfg
