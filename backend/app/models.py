import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    """登录用户。"""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="登录用户名，唯一")
    full_name: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="用户姓名（展示）")
    education_stage: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="教育阶段：primary/junior/senior/university"
    )
    enrollment_year: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="入学年份")
    gender: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="性别：male 男 / female 女，未设置时默认头像为男"
    )
    avatar_path: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="自定义头像相对上传目录路径，空则按性别使用内置默认图"
    )
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False, comment="bcrypt 密码哈希")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否管理员")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    mistakes: Mapped[list["Mistake"]] = relationship(back_populates="owner")
    review_settings: Mapped["UserReviewSettings | None"] = relationship(
        back_populates="user", uselist=False
    )


class Subject(Base):
    """科目：内置与自定义。"""

    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="科目显示名称")
    code: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="稳定编码，内置科目使用")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否内置，内置不建议删除")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="排序，越小越靠前")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    mistakes: Mapped[list["Mistake"]] = relationship(back_populates="subject")
    grade_subjects: Mapped[list["GradeSubject"]] = relationship(back_populates="subject")


class GradeLevel(Base):
    """年级：一至九年级与高一至高三（均为内置）。"""

    __tablename__ = "grade_levels"
    __table_args__ = (UniqueConstraint("level", name="uq_grade_level"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    level: Mapped[int] = mapped_column(Integer, nullable=False, comment="年级数字 1-12（10-12 为高一至高三）")
    name: Mapped[str] = mapped_column(String(32), nullable=False, comment="展示名称，如「一年级」")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否内置")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="排序")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    mistakes: Mapped[list["Mistake"]] = relationship(back_populates="grade")
    grade_subjects: Mapped[list["GradeSubject"]] = relationship(back_populates="grade")


class GradeSubject(Base):
    """年级与开设科目的对应关系。"""

    __tablename__ = "grade_subjects"
    __table_args__ = (UniqueConstraint("grade_level_id", "subject_id", name="uq_grade_subject"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    grade_level_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("grade_levels.id"), nullable=False, comment="年级 ID"
    )
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subjects.id"), nullable=False, comment="科目 ID"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="该年级下科目排序，越小越靠前"
    )

    grade: Mapped["GradeLevel"] = relationship(back_populates="grade_subjects")
    subject: Mapped["Subject"] = relationship(back_populates="grade_subjects")


class Mistake(Base):
    """错题记录。"""

    __tablename__ = "mistakes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, comment="所属用户，迁移前可能为空"
    )
    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id"), nullable=False, comment="科目 ID")
    grade_level_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("grade_levels.id"), nullable=False, comment="年级行 ID"
    )
    stem: Mapped[str] = mapped_column(Text, nullable=False, comment="题干文字")
    analysis: Mapped[str] = mapped_column(Text, default="", nullable=False, comment="解题思路")
    answer: Mapped[str] = mapped_column(Text, default="", nullable=False, comment="最终答案")
    image_path: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="原始图片相对 uploads 的路径")
    is_mastered: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否已掌握"
    )
    knowledge_tags: Mapped[list[str]] = mapped_column(
        JSON, default=lambda: [], nullable=False, comment="知识点标签 JSON 数组"
    )
    error_reason: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="错因 code：reading/concept 等，录入时必填"
    )
    mistake_source: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="错题来源 code：homework/monthly_exam/real_exam，录入时必填"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    owner: Mapped["User | None"] = relationship(back_populates="mistakes")
    subject: Mapped["Subject"] = relationship(back_populates="mistakes")
    grade: Mapped["GradeLevel"] = relationship(back_populates="mistakes")
    review_state: Mapped["MistakeReview | None"] = relationship(
        back_populates="mistake", uselist=False
    )


class UserReviewSettings(Base):
    """用户复习计划偏好（通用设置）。"""

    __tablename__ = "user_review_settings"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), primary_key=True, comment="用户 ID"
    )
    include_mastered_in_review: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否将已掌握题纳入复习计划"
    )
    daily_review_target: Mapped[int] = mapped_column(
        Integer, default=10, nullable=False, comment="每日复习目标题数"
    )
    review_grade_level_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("grade_levels.id"), nullable=True, comment="复习范围：年级 ID"
    )
    review_subject_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("subjects.id"), nullable=True, comment="复习范围：科目 ID"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="review_settings")


class MistakeReview(Base):
    """单道错题的复习调度状态。"""

    __tablename__ = "mistake_reviews"
    __table_args__ = (UniqueConstraint("mistake_id", name="uq_mistake_review_mistake"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True, comment="用户 ID"
    )
    mistake_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("mistakes.id"), nullable=False, comment="错题 ID"
    )
    review_stage: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="复习阶段（0 起，影响下次间隔）"
    )
    next_review_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="下次应复习时间（UTC）"
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="上次复习时间"
    )
    last_result: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="上次结果：good / again"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    mistake: Mapped["Mistake"] = relationship(back_populates="review_state")


class ReviewSession(Base):
    """一次复习打卡会话（按日、范围统计）。"""

    __tablename__ = "review_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True, comment="用户 ID"
    )
    review_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="复习打卡日期（UTC 日期）"
    )
    grade_level_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("grade_levels.id"), nullable=True, comment="本次范围年级"
    )
    subject_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("subjects.id"), nullable=True, comment="本次范围科目"
    )
    completed_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="本次已完成复习题数"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    items: Mapped[list["ReviewSessionItem"]] = relationship(back_populates="session")


class ReviewSessionItem(Base):
    """复习会话中的单题记录。"""

    __tablename__ = "review_session_items"
    __table_args__ = (UniqueConstraint("session_id", "mistake_id", name="uq_review_session_mistake"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("review_sessions.id"), nullable=False, index=True, comment="会话 ID"
    )
    mistake_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("mistakes.id"), nullable=False, comment="错题 ID"
    )
    result: Mapped[str] = mapped_column(String(16), nullable=False, comment="结果：good / again")
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped["ReviewSession"] = relationship(back_populates="items")


class AiProviderPreset(Base):
    """内置 AI 厂商预设（只读种子）。"""

    __tablename__ = "ai_provider_presets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="预设标识，如 openai")
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="界面展示名")
    protocol: Mapped[str] = mapped_column(String(32), default="openai_compatible", nullable=False, comment="协议类型")
    default_base_url: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="默认 Base URL")
    models_path: Mapped[str] = mapped_column(String(128), default="/models", nullable=False, comment="模型列表路径")
    chat_path: Mapped[str] = mapped_column(String(128), default="/chat/completions", nullable=False, comment="对话路径")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AiProviderConfig(Base):
    """用户配置的 AI 接入（可多套，一套激活）。"""

    __tablename__ = "ai_provider_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True, comment="所属用户"
    )
    user_label: Mapped[str] = mapped_column(String(128), nullable=False, comment="用户备注名")
    preset_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("ai_provider_presets.id"), nullable=True, comment="关联预设，自定义为空"
    )
    base_url: Mapped[str] = mapped_column(String(512), nullable=False, comment="实际请求 Base URL")
    models_path: Mapped[str] = mapped_column(String(128), default="/models", nullable=False)
    chat_path: Mapped[str] = mapped_column(String(128), default="/chat/completions", nullable=False)
    api_key_cipher: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, comment="加密后的 API Key")
    selected_model: Mapped[str | None] = mapped_column(String(256), nullable=True, comment="默认模型（识图/解题未单独指定时使用）")
    selected_model_vision: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="识图/OCR 专用模型，空则使用默认模型"
    )
    selected_model_solve: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="解题与分类专用模型，空则使用默认模型"
    )
    vision_preset_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("ai_provider_presets.id"), nullable=True, comment="识图独立接入时的预设"
    )
    vision_base_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="识图独立接入 Base URL，空则与主配置相同"
    )
    vision_api_key_cipher: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True, comment="识图独立接入的 API Key"
    )
    solve_preset_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("ai_provider_presets.id"), nullable=True, comment="解题独立接入时的预设"
    )
    solve_base_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="解题独立接入 Base URL，空则与主配置相同"
    )
    solve_api_key_cipher: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True, comment="解题独立接入的 API Key"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否为当前使用的配置")
    extra_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, comment="扩展字段")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
