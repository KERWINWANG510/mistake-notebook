import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
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
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False, comment="bcrypt 密码哈希")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否管理员")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    mistakes: Mapped[list["Mistake"]] = relationship(back_populates="owner")


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    owner: Mapped["User | None"] = relationship(back_populates="mistakes")
    subject: Mapped["Subject"] = relationship(back_populates="mistakes")
    grade: Mapped["GradeLevel"] = relationship(back_populates="mistakes")


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
