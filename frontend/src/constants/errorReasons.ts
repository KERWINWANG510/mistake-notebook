/** 错题错因选项（与后端 error_reasons.py 保持一致） */
export const ERROR_REASON_OPTIONS = [
  { label: "没看清题目", value: "reading" },
  { label: "知识没学会", value: "concept" },
  { label: "解题思路错", value: "method" },
  { label: "粗心算错了", value: "careless" },
] as const;

/** 已废弃 code → 合并后的 code（旧数据展示用） */
const LEGACY_ERROR_REASON_MAP: Record<string, string> = {
  formula: "method",
  memory: "concept",
  calculation: "careless",
};

export type ErrorReasonCode = (typeof ERROR_REASON_OPTIONS)[number]["value"];

function canonicalErrorReason(code: string | null | undefined): string | null {
  if (!code?.trim()) return null;
  const c = code.trim();
  return LEGACY_ERROR_REASON_MAP[c] ?? c;
}

export function errorReasonLabel(code: string | null | undefined): string {
  if (!code) return "";
  const canonical = canonicalErrorReason(code);
  const hit = ERROR_REASON_OPTIONS.find((o) => o.value === canonical);
  return hit?.label ?? code;
}
