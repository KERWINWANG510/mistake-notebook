/** 解析并校验应用内 returnTo 路径（禁止外链） */
export function parseAppReturnTo(query: Record<string, unknown>): string | null {
  const raw = query.returnTo;
  const candidate = Array.isArray(raw) ? raw[0] : raw;
  if (typeof candidate !== "string") return null;
  const path = candidate.trim();
  if (!path.startsWith("/") || path.startsWith("//") || path.includes("://")) return null;

  const allowedPrefixes = [
    "/mistakes",
    "/search",
    "/review",
    "/stats",
    "/grade-subjects",
    "/practice",
    "/settings",
  ];
  const ok = allowedPrefixes.some(
    (p) => path === p || path.startsWith(`${p}?`) || path.startsWith(`${p}/`),
  );
  return ok ? path : null;
}

export function returnBackLabel(returnPath: string | null): string {
  if (!returnPath) return "返回列表";
  if (returnPath.startsWith("/search")) return "返回搜索";
  if (returnPath.startsWith("/review")) return "返回复习";
  if (returnPath.startsWith("/stats")) return "返回统计";
  if (returnPath.startsWith("/practice")) return "返回模拟卷";
  if (returnPath.startsWith("/settings")) return "返回设置";
  if (returnPath.startsWith("/grade-subjects")) return "返回年级科目";
  if (returnPath.startsWith("/mistakes") && !returnPath.includes("/mistakes/")) return "返回错题本";
  return "返回";
}
