"""启动时种子数据：内置科目、年级、AI 预设。"""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AiProviderPreset, GradeLevel, GradeSubject, Mistake, Subject, User
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
    ("政治", "politics", 4),
    ("历史", "history", 5),
    ("地理", "geography", 6),
    ("物理", "physics", 7),
    ("化学", "chemistry", 8),
    ("生物", "biology", 9),
]


def builtin_subject_codes_for_level(level: int) -> list[str]:
    """按中国大陆 K12 常见课表返回各年级重要科目编码。

    - 小学 1–6：语数英
    - 初中 7：语数英 + 政史地 + 生物
    - 初中 8：+ 物理
    - 初中 9：+ 化学
    - 高中 10–12：语数英 + 政史地 + 理化生
    """
    base = ["chinese", "math", "english"]
    if 1 <= level <= 6:
        return base
    if 7 <= level <= 9:
        codes = base + ["politics", "history", "geography", "biology"]
        if level >= 8:
            codes.append("physics")
        if level >= 9:
            codes.append("chemistry")
        return codes
    if 10 <= level <= 12:
        return base + ["politics", "history", "geography", "physics", "chemistry", "biology"]
    return base


def _num_cn(n: int) -> str:
    m = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
    if 1 <= n <= 9:
        return m[n]
    return str(n)


# (level, 展示名, sort_order)
BUILTIN_GRADES: list[tuple[int, str, int]] = [
    *((lv, f"{_num_cn(lv)}年级", lv) for lv in range(1, 10)),
    (10, "高一", 10),
    (11, "高二", 11),
    (12, "高三", 12),
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
        for level, name, order in BUILTIN_GRADES:
            session.add(GradeLevel(level=level, name=name, is_builtin=True, sort_order=order))
        await session.flush()

    await session.commit()


async def ensure_builtin_subjects(session: AsyncSession) -> None:
    """确保内置重要科目齐全（语数英、政史地、理化生）。"""
    for name, code, order in BUILTIN_SUBJECTS:
        result = await session.execute(select(Subject).where(Subject.code == code))
        row = result.scalar_one_or_none()
        if row is None:
            session.add(Subject(name=name, code=code, is_builtin=True, sort_order=order))
        else:
            row.name = name
            row.sort_order = order
            row.is_builtin = True
    await session.flush()


async def ensure_grade_subject_mappings(session: AsyncSession) -> None:
    """按年级课表同步 grade_subjects 映射。"""
    await ensure_builtin_subjects(session)
    grades = (await session.execute(select(GradeLevel).order_by(GradeLevel.level))).scalars().all()
    subjects = (await session.execute(select(Subject))).scalars().all()
    code_to_id = {s.code: s.id for s in subjects if s.code}

    for grade in grades:
        codes = builtin_subject_codes_for_level(grade.level)
        for idx, code in enumerate(codes):
            subject_id = code_to_id.get(code)
            if not subject_id:
                continue
            result = await session.execute(
                select(GradeSubject).where(
                    GradeSubject.grade_level_id == grade.id,
                    GradeSubject.subject_id == subject_id,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                session.add(
                    GradeSubject(
                        grade_level_id=grade.id,
                        subject_id=subject_id,
                        sort_order=idx + 1,
                    )
                )
            else:
                row.sort_order = idx + 1

    await session.commit()


async def ensure_builtin_grades(session: AsyncSession) -> None:
    """确保一至九年级与高一至高三存在，且均为内置；清理无错题引用的自定义年级。"""
    for level, name, order in BUILTIN_GRADES:
        result = await session.execute(select(GradeLevel).where(GradeLevel.level == level))
        row = result.scalar_one_or_none()
        if row is None:
            session.add(GradeLevel(level=level, name=name, is_builtin=True, sort_order=order))
        else:
            row.name = name
            row.sort_order = order
            row.is_builtin = True

    await session.flush()

    custom = await session.execute(select(GradeLevel).where(GradeLevel.is_builtin.is_(False)))
    for row in custom.scalars().all():
        used = await session.execute(select(Mistake).where(Mistake.grade_level_id == row.id).limit(1))
        if used.scalar_one_or_none() is None:
            session.delete(row)

    await session.commit()


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
