import { http } from "./http";

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

export type Mistake = {
  id: string;
  subject_id: string;
  grade_level_id: string;
  stem: string;
  analysis: string;
  answer: string;
  image_path: string | null;
  created_at: string;
  updated_at: string;
  subject_name?: string | null;
  grade_name?: string | null;
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
};

export type SolveSuggestResult = {
  analysis: string;
  answer: string;
  suggested_subject_code: string | null;
  suggested_grade_level: number | null;
};

export async function fetchSubjects() {
  const { data } = await http.get<Subject[]>("/api/subjects");
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

export async function createGrade(payload: { level: number; name: string; sort_order?: number }) {
  const { data } = await http.post<Grade>("/api/grades", payload);
  return data;
}

export async function deleteGrade(id: string) {
  await http.delete(`/api/grades/${id}`);
}

export async function fetchMistakes(params?: { subject_id?: string; grade_level_id?: string }) {
  const { data } = await http.get<Mistake[]>("/api/mistakes", { params });
  return data;
}

export async function fetchMistake(id: string) {
  const { data } = await http.get<Mistake>(`/api/mistakes/${id}`);
  return data;
}

export async function analyzeImage(
  file: File,
  opts?: { model?: string; model_vision?: string; model_solve?: string },
) {
  const fd = new FormData();
  fd.append("file", file);
  const params: Record<string, string> = {};
  if (opts?.model) params.model = opts.model;
  if (opts?.model_vision) params.model_vision = opts.model_vision;
  if (opts?.model_solve) params.model_solve = opts.model_solve;
  const { data } = await http.post<AnalyzeResult>("/api/analyze", fd, {
    params: Object.keys(params).length ? params : undefined,
  });
  return data;
}

export async function solveFromStem(stem: string) {
  const { data } = await http.post<SolveSuggestResult>("/api/analyze/solve-stem", { stem });
  return data;
}

export async function createMistake(payload: {
  subject_id: string;
  grade_level_id: string;
  stem: string;
  analysis: string;
  answer: string;
  image?: File | null;
}) {
  const fd = new FormData();
  fd.append("subject_id", payload.subject_id);
  fd.append("grade_level_id", payload.grade_level_id);
  fd.append("stem", payload.stem);
  fd.append("analysis", payload.analysis);
  fd.append("answer", payload.answer);
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
