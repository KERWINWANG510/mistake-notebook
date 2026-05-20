export type GenderCode = "male" | "female";

export const GENDER_OPTIONS: { label: string; value: GenderCode }[] = [
  { label: "男", value: "male" },
  { label: "女", value: "female" },
];

export function genderLabel(code: string | null | undefined): string {
  if (code === "female") return "女";
  if (code === "male") return "男";
  return "未设置";
}
