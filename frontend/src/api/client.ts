import { apiBase, getStoredToken, http } from "./http";

export type MeUser = {
  id: string;
  username: string;
  full_name: string | null;
  education_stage: string | null;
  enrollment_year: number | null;
  is_admin: boolean;
  created_at?: string;
};

export type EducationStageItem = {
  code: string;
  name: string;
};

export type Subject = {
  id: string;
  name: string;
  code: string | null;
  is_builtin: boolean;
  sort_order: number;
};

export type Grade = {
  id: string;
  level: number;
  name: string;
  is_builtin: boolean;
  sort_order: number;
};

export type GradeSubjectBrief = {
  id: string;
  name: string;
  code: string | null;
  sort_order: number;
};

export type GradeWithSubjects = {
  id: string;
  level: number;
  name: string;
  sort_order: number;
  subjects: GradeSubjectBrief[];
};

export type Mistake = {
  id: string;
  subject_id: string;
  grade_level_id: string;
  stem: string;
  analysis: string;
  answer: string;
  image_path: string | null;
  is_mastered: boolean;
  knowledge_tags: string[];
  created_at: string;
  updated_at: string;
  subject_name?: string | null;
  grade_name?: string | null;
};

export type KnowledgeTagCount = {
  tag: string;
  count: number;
};

export type SubjectMistakeSummary = {
  subject_id: string;
  subject_name: string;
  subject_code: string | null;
  mistake_count: number;
  knowledge_tags: KnowledgeTagCount[];
};

export type MistakeStatsGradeRow = {
  grade_level_id: string;
  grade_name: string;
  level: number;
  mistake_count: number;
};

export type MistakeStatsSubjectRow = {
  subject_id: string;
  subject_name: string;
  mistake_count: number;
};

export type MistakeStatsTagRow = {
  tag: string;
  mistake_count: number;
};

export type MistakeStatsOverview = {
  /** 累计错题数量（含已掌握与未掌握） */
  total_mistake_count: number;
  /** 已掌握错题数量 */
  mastered_count: number;
  /** 掌握率（已掌握/累计×100；无错题时为 0） */
  mastery_rate_percent: number;
  by_grade: MistakeStatsGradeRow[];
  by_subject: MistakeStatsSubjectRow[];
  by_tag: MistakeStatsTagRow[];
};

export type AiPreset = {
  id: string;
  display_name: string;
  protocol: string;
  default_base_url: string | null;
  models_path: string;
  chat_path: string;
  sort_order: number;
};

export type AiConfig = {
  id: string;
  user_label: string;
  preset_id: string | null;
  base_url: string;
  models_path: string;
  chat_path: string;
  selected_model: string | null;
  selected_model_vision?: string | null;
  selected_model_solve?: string | null;
  vision_preset_id?: string | null;
  vision_base_url?: string | null;
  has_vision_api_key?: boolean;
  solve_preset_id?: string | null;
  solve_base_url?: string | null;
  has_solve_api_key?: boolean;
  is_active: boolean;
  has_api_key: boolean;
  created_at: string;
  updated_at: string;
};

export type AnalyzeResult = {
  stem: string;
  analysis: string;
  answer: string;
  suggested_subject_code: string | null;
  suggested_grade_level: number | null;
  knowledge_tags: string[];
};

/** 错题图片流式识别：NDJSON 行事件（与后端 /api/analyze/stream 一致） */
export type AnalyzeStreamEvent =
  | { type: "phase"; phase: "ocr" | "layout" | "solve"; label: string }
  | { type: "delta"; phase: "ocr" | "solve"; text: string }
  | { type: "stem"; text: string }
  | {
      type: "done";
      stem: string;
      analysis: string;
      answer: string;
      suggested_subject_code: string | null;
      suggested_grade_level: number | null;
      knowledge_tags: string[];
    }
  | { type: "error"; message: string };

export type SolveSuggestResult = {
  analysis: string;
  answer: string;
  suggested_subject_code: string | null;
  suggested_grade_level: number | null;
  knowledge_tags: string[];
};

export type PracticeDifficulty = "easy" | "medium" | "hard" | "challenge";

export type PracticeGenerateResult = {
  question_stem: string;
  reference_answer: string;
  reference_analysis: string;
};

export type PracticeCheckResult = {
  verdict: "correct" | "partial" | "wrong" | string;
  feedback: string;
  standard_answer: string;
  explanation: string;
};

export async function fetchAppVersion() {
  const { data } = await http.get<{ version: string }>("/api/version");
  return data.version;
}

export async function fetchSubjects(params?: { grade_level_id?: string }) {
  const { data } = await http.get<Subject[]>("/api/subjects", { params });
  return data;
}

export async function createSubject(payload: { name: string; code?: string | null }) {
  const { data } = await http.post<Subject>("/api/subjects", payload);
  return data;
}

export async function deleteSubject(id: string) {
  await http.delete(`/api/subjects/${id}`);
}

export async function fetchGrades() {
  const { data } = await http.get<Grade[]>("/api/grades");
  return data;
}

export async function fetchGradeCatalog() {
  const { data } = await http.get<GradeWithSubjects[]>("/api/grades/catalog");
  return data;
}

export async function fetchMistakes(params?: {
  subject_id?: string;
  grade_level_id?: string;
  mastery?: "mastered" | "unmastered" | "all";
  knowledge_tag?: string;
}) {
  const { data } = await http.get<Mistake[]>("/api/mistakes", { params });
  return data;
}

export async function fetchSubjectMistakeSummary(gradeLevelId: string) {
  const { data } = await http.get<SubjectMistakeSummary[]>("/api/mistakes/summary/by-subject", {
    params: { grade_level_id: gradeLevelId },
  });
  return data;
}

export async function fetchMistakeStatsOverview() {
  const { data } = await http.get<MistakeStatsOverview>("/api/stats/mistakes");
  return data;
}

export async function fetchMistakeStatsTags(params?: {
  subject_id?: string;
  grade_level_id?: string;
}) {
  const { data } = await http.get<MistakeStatsTagRow[]>("/api/stats/mistakes/tags", { params });
  return data;
}

export async function fetchMistake(id: string) {
  const { data } = await http.get<Mistake>(`/api/mistakes/${id}`);
  return data;
}

export async function analyzeImage(
  file: File,
  opts?: { model?: string; model_vision?: string; model_solve?: string; ocr_hint?: string },
) {
  const fd = new FormData();
  fd.append("file", file);
  const hint = opts?.ocr_hint?.trim();
  if (hint) fd.append("ocr_hint", hint);
  const params: Record<string, string> = {};
  if (opts?.model) params.model = opts.model;
  if (opts?.model_vision) params.model_vision = opts.model_vision;
  if (opts?.model_solve) params.model_solve = opts.model_solve;
  const { data } = await http.post<AnalyzeResult>("/api/analyze", fd, {
    params: Object.keys(params).length ? params : undefined,
  });
  return data;
}

/**
 * 流式识别题目图片：通过 onEvent 推送阶段与增量文本，解析完成后返回与 {@link analyzeImage} 相同结构的结果。
 */
export async function analyzeImageStream(
  file: File,
  onEvent: (ev: AnalyzeStreamEvent) => void,
  opts?: { model?: string; model_vision?: string; model_solve?: string; ocr_hint?: string },
  signal?: AbortSignal,
): Promise<AnalyzeResult> {
  const fd = new FormData();
  fd.append("file", file);
  const hint = opts?.ocr_hint?.trim();
  if (hint) fd.append("ocr_hint", hint);
  const qs = new URLSearchParams();
  if (opts?.model) qs.set("model", opts.model);
  if (opts?.model_vision) qs.set("model_vision", opts.model_vision);
  if (opts?.model_solve) qs.set("model_solve", opts.model_solve);
  const q = qs.toString();
  const base = apiBase.replace(/\/$/, "");
  const url = `${base}/api/analyze/stream${q ? `?${q}` : ""}`;
  const headers: Record<string, string> = {};
  const token = getStoredToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(url, {
    method: "POST",
    body: fd,
    headers,
    signal,
  });

  if (!res.ok) {
    const raw = await res.text();
    let msg = `识别请求失败（HTTP ${res.status}）`;
    try {
      const j = JSON.parse(raw) as { detail?: unknown };
      const d = j.detail;
      if (typeof d === "string") msg = d;
      else if (Array.isArray(d))
        msg = d.map((x: { msg?: string }) => x.msg ?? JSON.stringify(x)).join("；");
    } catch {
      if (raw.trim()) msg = raw.slice(0, 500);
    }
    throw new Error(msg);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("无法读取识别响应流");

  const dec = new TextDecoder();
  let buf = "";
  let result: AnalyzeResult | null = null;

  const handleLine = (line: string) => {
    const t = line.trim();
    if (!t) return;
    let ev: AnalyzeStreamEvent;
    try {
      ev = JSON.parse(t) as AnalyzeStreamEvent;
    } catch {
      return;
    }
    onEvent(ev);
    if (ev.type === "error") {
      throw new Error(ev.message);
    }
    if (ev.type === "done") {
      result = {
        stem: ev.stem,
        analysis: ev.analysis,
        answer: ev.answer,
        suggested_subject_code: ev.suggested_subject_code,
        suggested_grade_level: ev.suggested_grade_level,
        knowledge_tags: ev.knowledge_tags ?? [],
      };
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() ?? "";
    for (const line of lines) {
      handleLine(line);
    }
  }
  const tail = buf + dec.decode();
  if (tail.trim()) {
    for (const line of tail.split("\n")) {
      handleLine(line);
    }
  }

  if (!result) {
    throw new Error("连接已结束但未收到完整识别结果");
  }
  return result;
}

export async function solveFromStem(
  stem: string,
  opts?: { subject_code?: string | null; grade_level?: number | null },
) {
  const { data } = await http.post<SolveSuggestResult>("/api/analyze/solve-stem", {
    stem,
    subject_code: opts?.subject_code ?? undefined,
    grade_level: opts?.grade_level ?? undefined,
  });
  return data;
}

export async function generatePractice(mistakeId: string, difficulty: PracticeDifficulty) {
  const { data } = await http.post<PracticeGenerateResult>("/api/practice/generate", {
    mistake_id: mistakeId,
    difficulty,
  });
  return data;
}

export async function checkPractice(payload: {
  mistakeId: string;
  questionStem: string;
  referenceAnswer: string;
  referenceAnalysis: string;
  userAnswer: string;
  image?: File | null;
}) {
  const fd = new FormData();
  fd.append("mistake_id", payload.mistakeId);
  fd.append("question_stem", payload.questionStem);
  fd.append("reference_answer", payload.referenceAnswer);
  fd.append("reference_analysis", payload.referenceAnalysis);
  fd.append("user_answer", payload.userAnswer);
  if (payload.image) fd.append("file", payload.image);
  const { data } = await http.post<PracticeCheckResult>("/api/practice/check", fd);
  return data;
}

export async function createMistake(payload: {
  subject_id: string;
  grade_level_id: string;
  stem: string;
  analysis: string;
  answer: string;
  knowledge_tags?: string[];
  image?: File | null;
}) {
  const fd = new FormData();
  fd.append("subject_id", payload.subject_id);
  fd.append("grade_level_id", payload.grade_level_id);
  fd.append("stem", payload.stem);
  fd.append("analysis", payload.analysis);
  fd.append("answer", payload.answer);
  fd.append("knowledge_tags", JSON.stringify(payload.knowledge_tags ?? []));
  if (payload.image) fd.append("image", payload.image);
  const { data } = await http.post<Mistake>("/api/mistakes", fd);
  return data;
}

export async function updateMistake(
  id: string,
  payload: Partial<{
    subject_id: string;
    grade_level_id: string;
    stem: string;
    analysis: string;
    answer: string;
    is_mastered: boolean;
    knowledge_tags: string[];
  }>,
) {
  const { data } = await http.patch<Mistake>(`/api/mistakes/${id}`, payload);
  return data;
}

export async function deleteMistake(id: string) {
  await http.delete(`/api/mistakes/${id}`);
}

export async function fetchMistakeImageObjectUrl(mistakeId: string): Promise<string> {
  const { data } = await http.get<Blob>(`/api/mistakes/${mistakeId}/image`, { responseType: "blob" });
  return URL.createObjectURL(data);
}

export async function replaceMistakeImage(mistakeId: string, image: File) {
  const fd = new FormData();
  fd.append("image", image);
  const { data } = await http.post<Mistake>(`/api/mistakes/${mistakeId}/image`, fd);
  return data;
}

export async function fetchEducationStages() {
  const { data } = await http.get<EducationStageItem[]>("/api/auth/education-stages");
  return data;
}

export async function fetchUserList() {
  const { data } = await http.get<MeUser[]>("/api/auth/users");
  return data;
}

export async function createUserAccount(payload: {
  username: string;
  password: string;
  full_name: string;
  education_stage: string;
  enrollment_year: number;
}) {
  const { data } = await http.post<MeUser>("/api/auth/users", payload);
  return data;
}

export async function updateUserAccount(
  id: string,
  payload: {
    username?: string;
    password?: string;
    full_name?: string;
    education_stage?: string;
    enrollment_year?: number;
    is_admin?: boolean;
  },
) {
  const { data } = await http.patch<MeUser>(`/api/auth/users/${id}`, payload);
  return data;
}

export async function deleteUserAccount(id: string) {
  const { data } = await http.delete<{ status: string }>(`/api/auth/users/${id}`);
  return data;
}

export async function fetchAiPresets() {
  const { data } = await http.get<AiPreset[]>("/api/ai/presets");
  return data;
}

export async function fetchAiConfigs() {
  const { data } = await http.get<AiConfig[]>("/api/ai/configs");
  return data;
}

export async function createAiConfig(payload: {
  user_label: string;
  preset_id?: string | null;
  base_url: string;
  models_path?: string;
  chat_path?: string;
  api_key?: string | null;
  selected_model?: string | null;
  selected_model_vision?: string | null;
  selected_model_solve?: string | null;
  vision_preset_id?: string | null;
  vision_base_url?: string | null;
  vision_api_key?: string | null;
  solve_preset_id?: string | null;
  solve_base_url?: string | null;
  solve_api_key?: string | null;
}) {
  const { data } = await http.post<AiConfig>("/api/ai/configs", payload);
  return data;
}

export async function updateAiConfig(
  id: string,
  payload: Partial<{
    user_label: string;
    base_url: string;
    models_path: string;
    chat_path: string;
    api_key: string | null;
    selected_model: string | null;
    selected_model_vision: string | null;
    selected_model_solve: string | null;
    vision_preset_id: string | null;
    vision_base_url: string | null;
    vision_api_key: string | null;
    solve_preset_id: string | null;
    solve_base_url: string | null;
    solve_api_key: string | null;
  }>,
) {
  const { data } = await http.patch<AiConfig>(`/api/ai/configs/${id}`, payload);
  return data;
}

export async function deleteAiConfig(id: string) {
  await http.delete(`/api/ai/configs/${id}`);
}

export async function activateAiConfig(id: string) {
  const { data } = await http.post<AiConfig>(`/api/ai/configs/${id}/activate`);
  return data;
}

export type ModelItem = { id: string; raw?: Record<string, unknown> | null };

export async function listAiModels(configId: string, target: "main" | "vision" | "solve" = "main") {
  const { data } = await http.post<{
    ok: boolean;
    models: ModelItem[];
    error_code?: string | null;
    message?: string | null;
  }>(`/api/ai/configs/${configId}/list-models`, {}, { params: { target } });
  return data;
}

/** 未保存配置时，用表单中的地址与密钥临时拉取模型列表 */
export async function listAiModelsPreview(payload: {
  base_url: string;
  models_path: string;
  api_key: string;
}) {
  const { data } = await http.post<{
    ok: boolean;
    models: ModelItem[];
    error_code?: string | null;
    message?: string | null;
  }>("/api/ai/list-models-preview", payload);
  return data;
}
