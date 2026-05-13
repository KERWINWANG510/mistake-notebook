"""启动时种子数据：内置科目、年级、AI 预设。"""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AiProviderPreset, GradeLevel, Subject, User
from app.services.password import hash_password


PRESETS: list[dict] = [
    {
        "id": "openai",
        "display_name": "OpenAI",
        "protocol": "openai_compatible",
        "default_base_url": "https://api.openai.com/v1",
        "models_path": "/models",
        "chat_path": "/chat/completions",
        "sort_order": 10,
    },
    {
        "id": "deepseek",
        "display_name": "DeepSeek",
        "protocol": "openai_compatible",
        "default_base_url": "https://api.deepseek.com/v1",
        "models_path": "/models",
        "chat_path": "/chat/completions",
        "sort_order": 20,
    },
    {
        "id": "moonshot",
        "display_name": "Moonshot（Kimi）",
        "protocol": "openai_compatible",
        "default_base_url": "https://api.moonshot.cn/v1",
        "models_path": "/models",
        "chat_path": "/chat/completions",
        "sort_order": 30,
    },
    {
        "id": "zhipu",
        "display_name": "智谱 GLM",
        "protocol": "openai_compatible",
        "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models_path": "/models",
        "chat_path": "/chat/completions",
        "sort_order": 40,
    },
    {
        "id": "siliconflow",
        "display_name": "硅基流动",
        "protocol": "openai_compatible",
        "default_base_url": "https://api.siliconflow.cn/v1",
        "models_path": "/models",
        "chat_path": "/chat/completions",
        "sort_order": 50,
    },
    {
        "id": "dashscope_bailian",
        "display_name": "阿里百炼（OpenAI 兼容）",
        "protocol": "openai_compatible",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models_path": "/models",
        "chat_path": "/chat/completions",
        "sort_order": 55,
    },
    {
        "id": "local_ollama",
        "display_name": "本地 Ollama（OpenAI 兼容）",
        "protocol": "openai_compatible",
        "default_base_url": "http://127.0.0.1:11434/v1",
        "models_path": "/models",
        "chat_path": "/chat/completions",
        "sort_order": 90,
    },
    {
        "id": "custom_openai",
        "display_name": "自定义 OpenAI 兼容",
        "protocol": "openai_compatible",
        "default_base_url": None,
        "models_path": "/models",
        "chat_path": "/chat/completions",
        "sort_order": 100,
    },
]

BUILTIN_SUBJECTS: list[tuple[str, str, int]] = [
    ("语文", "chinese", 1),
    ("数学", "math", 2),
    ("英语", "english", 3),
]


async def run_seed(session: AsyncSession) -> None:
    result = await session.execute(select(AiProviderPreset).limit(1))
    if result.scalar_one_or_none() is None:
        for p in PRESETS:
            session.add(AiProviderPreset(**p))
        await session.flush()

    result = await session.execute(select(Subject).limit(1))
    if result.scalar_one_or_none() is None:
        for name, code, order in BUILTIN_SUBJECTS:
            session.add(Subject(name=name, code=code, is_builtin=True, sort_order=order))
        await session.flush()

    result = await session.execute(select(GradeLevel).limit(1))
    if result.scalar_one_or_none() is None:
        for lv in range(1, 10):
            session.add(
                GradeLevel(level=lv, name=f"{_num_cn(lv)}年级", is_builtin=True, sort_order=lv)
            )
        await session.flush()

    await session.commit()


def _num_cn(n: int) -> str:
    m = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
    if 1 <= n <= 9:
        return m[n]
    return str(n)


async def ensure_missing_presets(session: AsyncSession) -> None:
    """为已存在的老库补充新增的厂商预设（如阿里百炼）。"""
    for p in PRESETS:
        row = await session.get(AiProviderPreset, p["id"])
        if row is None:
            session.add(AiProviderPreset(**p))
    await session.commit()


async def ensure_admin_user(session: AsyncSession) -> None:
    """内置管理员 admin / 123456，仅在无 admin 时创建。"""
    from datetime import datetime

    r = await session.execute(select(User).where(User.username == "admin"))
    if r.scalar_one_or_none():
        return
    y = datetime.utcnow().year
    session.add(
        User(
            username="admin",
            password_hash=hash_password("123456"),
            is_admin=True,
            full_name="系统管理员",
            education_stage="university",
            enrollment_year=y,
        )
    )
    await session.commit()


async def backfill_user_profiles(session: AsyncSession) -> None:
    """为已有账号（如迁移前的 admin）补全姓名与教育信息。"""
    from datetime import datetime

    y = datetime.utcnow().year
    r = await session.execute(select(User).where(User.username == "admin"))
    admin = r.scalar_one_or_none()
    if admin is None:
        return
    changed = False
    if not (admin.full_name or "").strip():
        admin.full_name = "系统管理员"
        changed = True
    if not admin.education_stage:
        admin.education_stage = "university"
        changed = True
    if admin.enrollment_year is None:
        admin.enrollment_year = y
        changed = True
    if changed:
        await session.commit()


async def backfill_mistake_user_ids(session: AsyncSession) -> None:
    """将历史错题归属到 admin 账号。"""
    r = await session.execute(select(User).where(User.username == "admin"))
    admin = r.scalar_one_or_none()
    if admin is None:
        return
    await session.execute(text("UPDATE mistakes SET user_id = :uid WHERE user_id IS NULL"), {"uid": admin.id})
    await session.commit()
