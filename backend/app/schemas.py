from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


EducationStageCode = Literal["primary", "junior", "senior", "university"]


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    username: str
    full_name: str | None = None
    education_stage: str | None = None
    enrollment_year: int | None = None
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreateBody(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=4, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=64)
    education_stage: EducationStageCode
    enrollment_year: int = Field(..., ge=1980, le=2050)


class UserUpdateBody(BaseModel):
    username: str | None = Field(None, min_length=2, max_length=64)
    password: str | None = Field(None, min_length=4, max_length=128)
    full_name: str | None = Field(None, min_length=1, max_length=64)
    education_stage: EducationStageCode | None = None
    enrollment_year: int | None = Field(None, ge=1980, le=2050)
    is_admin: bool | None = None


class EducationStageOut(BaseModel):
    code: str
    name: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


class SubjectOut(BaseModel):
    id: str
    name: str
    code: str | None
    is_builtin: bool
    sort_order: int

    model_config = {"from_attributes": True}


class SubjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    code: str | None = Field(None, max_length=32)


class SubjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    sort_order: int | None = None


class GradeOut(BaseModel):
    id: str
    level: int
    name: str
    is_builtin: bool
    sort_order: int

    model_config = {"from_attributes": True}


class GradeCreate(BaseModel):
    level: int = Field(..., ge=1, le=12)
    name: str = Field(..., min_length=1, max_length=32)
    sort_order: int | None = None


class GradeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=32)
    sort_order: int | None = None


class MistakeOut(BaseModel):
    id: str
    subject_id: str
    grade_level_id: str
    stem: str
    analysis: str
    answer: str
    image_path: str | None
    is_mastered: bool = False
    created_at: datetime
    updated_at: datetime
    subject_name: str | None = None
    grade_name: str | None = None

    model_config = {"from_attributes": True}


class MistakeCreate(BaseModel):
    subject_id: str
    grade_level_id: str
    stem: str
    analysis: str = ""
    answer: str = ""


class MistakeUpdate(BaseModel):
    subject_id: str | None = None
    grade_level_id: str | None = None
    stem: str | None = None
    analysis: str | None = None
    answer: str | None = None
    is_mastered: bool | None = None


class SubjectMistakeSummary(BaseModel):
    subject_id: str
    subject_name: str
    subject_code: str | None = None
    mistake_count: int


class AiPresetOut(BaseModel):
    id: str
    display_name: str
    protocol: str
    default_base_url: str | None
    models_path: str
    chat_path: str
    sort_order: int

    model_config = {"from_attributes": True}


class AiConfigOut(BaseModel):
    id: str
    user_label: str
    preset_id: str | None
    base_url: str
    models_path: str
    chat_path: str
    selected_model: str | None
    selected_model_vision: str | None = None
    selected_model_solve: str | None = None
    vision_preset_id: str | None = None
    vision_base_url: str | None = None
    has_vision_api_key: bool = False
    solve_preset_id: str | None = None
    solve_base_url: str | None = None
    has_solve_api_key: bool = False
    is_active: bool
    has_api_key: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AiConfigCreate(BaseModel):
    user_label: str = Field(..., min_length=1, max_length=128)
    preset_id: str | None = None
    base_url: str = Field(..., min_length=1, max_length=512)
    models_path: str = Field(default="/models", max_length=128)
    chat_path: str = Field(default="/chat/completions", max_length=128)
    api_key: str | None = Field(None, max_length=2048)
    selected_model: str | None = Field(None, max_length=256)
    selected_model_vision: str | None = Field(None, max_length=256)
    selected_model_solve: str | None = Field(None, max_length=256)
    vision_preset_id: str | None = Field(None, max_length=64)
    vision_base_url: str | None = Field(None, max_length=512)
    vision_api_key: str | None = Field(None, max_length=2048)
    solve_preset_id: str | None = Field(None, max_length=64)
    solve_base_url: str | None = Field(None, max_length=512)
    solve_api_key: str | None = Field(None, max_length=2048)


class AiConfigUpdate(BaseModel):
    user_label: str | None = Field(None, min_length=1, max_length=128)
    base_url: str | None = Field(None, min_length=1, max_length=512)
    models_path: str | None = Field(None, max_length=128)
    chat_path: str | None = Field(None, max_length=128)
    api_key: str | None = Field(None, max_length=2048)
    selected_model: str | None = Field(None, max_length=256)
    selected_model_vision: str | None = Field(None, max_length=256)
    selected_model_solve: str | None = Field(None, max_length=256)
    vision_preset_id: str | None = Field(None, max_length=64)
    vision_base_url: str | None = Field(None, max_length=512)
    vision_api_key: str | None = Field(None, max_length=2048)
    solve_preset_id: str | None = Field(None, max_length=64)
    solve_base_url: str | None = Field(None, max_length=512)
    solve_api_key: str | None = Field(None, max_length=2048)


class ModelItem(BaseModel):
    id: str
    raw: dict[str, Any] | None = None


class ListModelsResponse(BaseModel):
    ok: bool
    models: list[ModelItem] = Field(default_factory=list)
    error_code: str | None = None
    message: str | None = None


class ListModelsPreviewBody(BaseModel):
    """未保存配置时，用表单中的地址与密钥临时拉取模型列表（不落库）。"""

    base_url: str = Field(..., min_length=1, max_length=512)
    models_path: str = Field(default="/models", max_length=128)
    api_key: str = Field(..., min_length=1, max_length=2048)


class AnalyzeResult(BaseModel):
    stem: str
    analysis: str
    answer: str
    suggested_subject_code: str | None = None
    suggested_grade_level: int | None = Field(None, ge=1, le=12)


class SolveSuggestResult(BaseModel):
    """解题模型返回（不含题干）。"""

    analysis: str = ""
    answer: str = ""
    suggested_subject_code: str | None = None
    suggested_grade_level: int | None = Field(None, ge=1, le=12)


class OcrStemResult(BaseModel):
    stem: str


class SolveFromStemBody(BaseModel):
    stem: str = Field(..., min_length=1, max_length=20000)


PracticeDifficulty = Literal["easy", "medium", "hard", "challenge"]


class PracticeGenerateBody(BaseModel):
    mistake_id: str = Field(..., min_length=1, max_length=64)
    difficulty: PracticeDifficulty


class PracticeGenerateResult(BaseModel):
    question_stem: str
    reference_answer: str
    reference_analysis: str


class PracticeCheckResult(BaseModel):
    verdict: str
    feedback: str
    standard_answer: str
    explanation: str
