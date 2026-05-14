import type { Grade, MeUser } from "../api/client";

/** 与后端 education.STAGE_GRADE_RANGE 一致 */
const STAGE_GRADE_RANGE: Record<string, [number, number]> = {
  primary: [1, 6],
  junior: [7, 9],
  senior: [10, 12],
};

/**
 * 根据教育阶段与入学年份推断当前年级序号（9 月为新学年起点）。
 */
export function inferCurrentGradeLevel(
  user: Pick<MeUser, "education_stage" | "enrollment_year"> | null | undefined,
  now = new Date(),
): number | null {
  if (!user?.education_stage || user.enrollment_year == null) return null;
  const bounds = STAGE_GRADE_RANGE[user.education_stage];
  if (!bounds) return null;
  const academicStartYear = now.getMonth() + 1 >= 9 ? now.getFullYear() : now.getFullYear() - 1;
  let yearsInStage = academicStartYear - user.enrollment_year + 1;
  if (yearsInStage < 1) yearsInStage = 1;
  const [lo, hi] = bounds;
  return Math.max(lo, Math.min(hi, lo + yearsInStage - 1));
}

export function resolveGradeByLevel(level: number | null, grades: Grade[]): Grade | null {
  if (level == null) return null;
  return grades.find((g) => g.level === level) ?? null;
}

export function educationStageLabel(code: string | null | undefined): string {
  const map: Record<string, string> = {
    primary: "小学",
    junior: "初中",
    senior: "高中",
    university: "大学",
  };
  if (!code) return "";
  return map[code] ?? code;
}

export type SubjectAccent = {
  bg: string;
  fg: string;
  ring: string;
};

const SUBJECT_ACCENTS: Record<string, SubjectAccent> = {
  chinese: { bg: "linear-gradient(135deg, #fff1f2 0%, #ffe4e6 100%)", fg: "#e11d48", ring: "rgba(225, 29, 72, 0.22)" },
  math: { bg: "linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%)", fg: "#4f46e5", ring: "rgba(79, 70, 229, 0.22)" },
  english: { bg: "linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)", fg: "#059669", ring: "rgba(5, 150, 105, 0.22)" },
};

const DEFAULT_ACCENT: SubjectAccent = {
  bg: "linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)",
  fg: "#6366f1",
  ring: "rgba(99, 102, 241, 0.2)",
};

export function subjectAccent(code: string | null | undefined): SubjectAccent {
  if (!code) return DEFAULT_ACCENT;
  return SUBJECT_ACCENTS[code] ?? DEFAULT_ACCENT;
}

export function subjectInitial(name: string): string {
  return name.slice(0, 1);
}
