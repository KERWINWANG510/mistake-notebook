/** 错题来源选项（与后端 mistake_sources.py 保持一致） */
export const MISTAKE_SOURCE_OPTIONS = [
  { label: "作业", value: "homework" },
  { label: "月考", value: "monthly_exam" },
  { label: "真题", value: "real_exam" },
] as const;

export type MistakeSourceCode = (typeof MISTAKE_SOURCE_OPTIONS)[number]["value"];

export function mistakeSourceLabel(code: string | null | undefined): string {
  if (!code) return "";
  return MISTAKE_SOURCE_OPTIONS.find((o) => o.value === code)?.label ?? code;
}
