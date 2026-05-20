from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


EducationStageCode = Literal["primary", "junior", "senior", "university"]
GenderCode = Literal["male", "female"]


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    username: str
    full_name: str | None = None
    education_stage: str | None = None
    enrollment_year: int | None = None
    gender: str | None = None
    avatar_url: str
    has_custom_avatar: bool = False
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_user(cls, user) -> "UserOut":
        return cls(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            education_stage=user.education_stage,
            enrollment_year=user.enrollment_year,
            gender=user.gender,
            avatar_url=f"/api/auth/users/{user.id}/avatar",
            has_custom_avatar=bool(user.avatar_path),
            is_admin=user.is_admin,
            created_at=user.created_at,
        )


class UserCreateBody(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=4, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=64)
    education_stage: EducationStageCode
    enrollment_year: int = Field(..., ge=1980, le=2050)
    gender: GenderCode | None = None


class UserUpdateBody(BaseModel):
    username: str | None = Field(None, min_length=2, max_length=64)
    password: str | None = Field(None, min_length=4, max_length=128)
    full_name: str | None = Field(None, min_length=1, max_length=64)
    education_stage: EducationStageCode | None = None
    enrollment_year: int | None = Field(None, ge=1980, le=2050)
    gender: GenderCode | None = None
    clear_avatar: bool | None = None
    is_admin: bool | None = None


class UserProfileUpdateBody(BaseModel):
    """当前用户自助修改资料（不可改管理员标志）。"""

    username: str | None = Field(None, min_length=2, max_length=64)
    password: str | None = Field(None, min_length=4, max_length=128)
    full_name: str | None = Field(None, min_length=1, max_length=64)
    education_stage: EducationStageCode | None = None
    enrollment_year: int | None = Field(None, ge=1980, le=2050)
    gender: GenderCode | None = None
    clear_avatar: bool | None = None


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


class GradeSubjectBrief(BaseModel):
    id: str
    name: str
    code: str | None
    sort_order: int


class GradeWithSubjectsOut(BaseModel):
    id: str
    level: int
    name: str
    sort_order: int
    subjects: list[GradeSubjectBrief]


class ErrorReasonOptionOut(BaseModel):
    code: str
    label: str


class MistakeSourceOptionOut(BaseModel):
    code: str
    label: str


class MistakeOut(BaseModel):
    id: str
    subject_id: str
    grade_level_id: str
    stem: str
    analysis: str
    answer: str
    image_path: str | None
    is_mastered: bool = False
    knowledge_tags: list[str] = Field(default_factory=list)
    error_reason: str | None = None
    error_reason_label: str | None = None
    mistake_source: str | None = None
    mistake_source_label: str | None = None
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
    knowledge_tags: list[str] | None = None
    error_reason: str | None = None
    mistake_source: str | None = None


class KnowledgeTagCount(BaseModel):
    tag: str
    count: int


class MistakeStatsGradeRow(BaseModel):
    grade_level_id: str
    grade_name: str
    level: int
    mistake_count: int


class MistakeStatsSubjectRow(BaseModel):
    subject_id: str
    subject_name: str
    mistake_count: int


class MistakeStatsSourceRow(BaseModel):
    source_code: str
    source_label: str
    mistake_count: int


class MistakeStatsTagRow(BaseModel):
    tag: str
    mistake_count: int


class MistakeStatsErrorReasonHeatmap(BaseModel):
    """错因 × 科目热力图数据（ECharts heatmap：[x, y, value]）。"""

    reason_codes: list[str]
    reason_labels: list[str]
    subject_ids: list[str]
    subject_names: list[str]
    cells: list[list[int]] = Field(
        description="每项为 [subject_index, reason_index, mistake_count]"
    )
    annotated_mistake_count: int = Field(description="已标注错因的错题数量")
    total_mistake_count: int = Field(description="当前用户错题总数")


class MistakeStatsOverview(BaseModel):
    """错题统计总览：汇总指标 + 分维度分布。"""

    total_mistake_count: int = Field(description="累计错题数量（含已掌握与未掌握）")
    mastered_count: int = Field(description="已掌握错题数量")
    mastery_rate_percent: float = Field(description="掌握率（已掌握/累计×100；无错题时为 0）")
    by_grade: list[MistakeStatsGradeRow]
    by_subject: list[MistakeStatsSubjectRow]
    by_source: list[MistakeStatsSourceRow]
    by_tag: list[MistakeStatsTagRow]


class ReviewSettingsOut(BaseModel):
    include_mastered_in_review: bool = Field(description="是否将已掌握题纳入复习计划")
    daily_review_target: int = Field(description="每日复习目标题数", ge=1, le=200)
    review_grade_level_id: str | None = Field(None, description="复习范围年级 ID")
    review_subject_id: str | None = Field(None, description="复习范围科目 ID")
    review_grade_name: str | None = None
    review_subject_name: str | None = None


class ReviewSettingsUpdate(BaseModel):
    include_mastered_in_review: bool | None = None
    daily_review_target: int | None = Field(None, ge=1, le=200)
    review_grade_level_id: str | None = None
    review_subject_id: str | None = None


class ReviewTodayItemOut(BaseModel):
    mistake_id: str
    subject_id: str
    grade_level_id: str
    subject_name: str | None = None
    grade_name: str | None = None
    stem_preview: str
    analysis: str
    answer: str
    is_mastered: bool
    review_stage: int
    next_review_at: datetime
    image_path: str | None = None


class ReviewTodayOut(BaseModel):
    daily_target: int
    due_total: int
    today_completed: int
    streak_days: int
    items: list[ReviewTodayItemOut]
    settings: ReviewSettingsOut


class ReviewRecordBody(BaseModel):
    mistake_id: str
    result: Literal["good", "again"]
    grade_level_id: str | None = None
    subject_id: str | None = None


class ReviewRecordOut(BaseModel):
    mistake_id: str
    review_stage: int
    next_review_at: datetime
    today_completed: int
    streak_days: int


class ReviewStatsOut(BaseModel):
    streak_days: int
    today_completed: int
    daily_target: int
    due_total: int
    total_reviewed_all_time: int


class ReviewStatsDailyRow(BaseModel):
    date: str = Field(description="日期 YYYY-MM-DD")
    review_count: int = Field(description="当日完成复习题数")


class ReviewStatsResultRow(BaseModel):
    result_code: str
    result_label: str
    count: int


class ReviewStatsChartsOut(BaseModel):
    """统计页：今日复习相关指标与图表数据。"""

    streak_days: int = Field(description="连续打卡天数")
    today_completed: int = Field(description="今日已完成复习题数")
    daily_target: int = Field(description="每日复习目标")
    due_total: int = Field(description="当前待复习（今日到期）题数")
    total_reviewed_all_time: int = Field(description="累计复习做题次数")
    daily_trend: list[ReviewStatsDailyRow] = Field(description="近 N 日每日复习题数")
    by_result: list[ReviewStatsResultRow] = Field(description="复习结果分布（会了/再练练）")


class SubjectMistakeSummary(BaseModel):
    subject_id: str
    subject_name: str
    subject_code: str | None = None
    mistake_count: int
    knowledge_tags: list[KnowledgeTagCount] = Field(default_factory=list)


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
    knowledge_tags: list[str] = Field(default_factory=list)


class SolveSuggestResult(BaseModel):
    """解题模型返回（不含题干）。"""

    analysis: str = ""
    answer: str = ""
    suggested_subject_code: str | None = None
    suggested_grade_level: int | None = Field(None, ge=1, le=12)
    knowledge_tags: list[str] = Field(default_factory=list)


class OcrStemResult(BaseModel):
    stem: str


class SolveFromStemBody(BaseModel):
    stem: str = Field(..., min_length=1, max_length=20000)
    subject_code: str | None = Field(None, max_length=32)
    grade_level: int | None = Field(None, ge=1, le=12)


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


class MockPaperQuestionTypeItem(BaseModel):
    """模拟卷可选题型（与年级、科目关联）。"""

    code: str
    name: str


class MockPaperGenerateBody(BaseModel):
    """模拟练习卷生成请求。"""

    grade_level_id: str = Field(..., min_length=1, max_length=64)
    subject_id: str = Field(..., min_length=1, max_length=64)
    knowledge_tags: list[str] = Field(default_factory=list, max_length=12)
    question_type_codes: list[str] = Field(default_factory=list, max_length=20)
    counts_by_type: dict[str, int] = Field(default_factory=dict)
    total_score: int | None = Field(None, ge=20, le=200)
    use_answer_sheet: bool = Field(
        False,
        description="为 true 时配套生成答题卡页，题干不预留大段手写区；为 false 时在题干中预留作答空间",
    )


class MockPaperItemOut(BaseModel):
    """单道小题（全局题号唯一）。"""

    number: int = Field(..., ge=1, le=99)
    minor_index: int | None = Field(None, ge=1, le=99, description="大题内小题序号，用于「（1）（2）」展示")
    type_code: str
    type_name: str
    score: int = Field(..., ge=0, le=200)
    stem: str


class MockPaperSectionOut(BaseModel):
    """大题（与真实试卷分区一致）。"""

    section_order: int = Field(..., ge=1, le=20, description="大题序号，从 1 递增")
    heading: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="大题标题行，如「第一大题  选择题（本大题共24分）」",
    )
    section_score: int = Field(..., ge=0, le=200, description="该大题总分，应与各小题 score 之和基本一致")
    items: list[MockPaperItemOut] = Field(default_factory=list)


class MockPaperAnswerOut(BaseModel):
    number: int = Field(..., ge=1, le=99)
    answer: str


class MockPaperGenerateResult(BaseModel):
    title: str
    grade_name: str
    subject_name: str
    requested_total_score: int
    actual_total_score: int
    suggested_exam_minutes: int = Field(..., ge=10, le=240, description="AI 建议的本卷作答时间（分钟）")
    use_answer_sheet: bool = False
    instructions: str = ""
    sections: list[MockPaperSectionOut]
    answers: list[MockPaperAnswerOut]
