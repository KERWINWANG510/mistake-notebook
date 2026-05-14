function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function applyInlineStyles(line: string): string {
  return line
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/__(.+?)__/g, "<strong>$1</strong>");
}

function wrapLine(line: string): string {
  const trimmed = line.trim();
  if (!trimmed) return "";
  const html = applyInlineStyles(escapeHtml(trimmed));
  if (/^\d+[.、．)]\s/.test(trimmed)) {
    return `<p class="analysis-step">${html}</p>`;
  }
  if (/^[-•·]\s/.test(trimmed)) {
    return `<p class="analysis-bullet">${html}</p>`;
  }
  if (/^【.+】/.test(trimmed) || /^（\d+）/.test(trimmed)) {
    return `<p class="analysis-label">${html}</p>`;
  }
  return `<p>${html}</p>`;
}

/** 将解题思路纯文本（含简单 Markdown）转为可展示 HTML */
export function formatAnalysisHtml(text: string): string {
  const raw = text.trim();
  if (!raw) return "";

  const paragraphs = raw.split(/\n{2,}/);
  return paragraphs
    .map((block) => {
      const lines = block.split("\n").map((l) => l.trimEnd());
      const hasMultiline = lines.filter((l) => l.trim()).length > 1;
      if (!hasMultiline) {
        const line = lines.join("\n").trim();
        return line ? wrapLine(line) : "";
      }
      return lines.map((line) => (line.trim() ? wrapLine(line) : "")).join("");
    })
    .filter(Boolean)
    .join("");
}

const STEM_U_RE = /<u\b[^>]*>([\s\S]*?)<\/u>/gi;

/** 去掉 `<u>` 标签，用于与 {@link wrapLine} 相同的行首分类（题号、项目符号等）。 */
function stemPlainForWrapClass(line: string): string {
  return line.replace(new RegExp(STEM_U_RE.source, STEM_U_RE.flags), "$1");
}

/** 单行内：普通片段走 Markdown 轻量规则，`<u>` 内仅转义，全部拼成一段内联 HTML（不再按片段包 `<p>`）。 */
function stemLineToInlineHtml(line: string): string {
  const parts: { kind: "plain" | "u"; value: string }[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  const re = new RegExp(STEM_U_RE.source, STEM_U_RE.flags);
  while ((m = re.exec(line)) !== null) {
    if (m.index > last) parts.push({ kind: "plain", value: line.slice(last, m.index) });
    parts.push({ kind: "u", value: m[1] ?? "" });
    last = m.index + m[0].length;
  }
  if (last < line.length) parts.push({ kind: "plain", value: line.slice(last) });

  return parts
    .map((p) =>
      p.kind === "u" ? `<u>${escapeHtml(p.value)}</u>` : applyInlineStyles(escapeHtml(p.value)),
    )
    .join("");
}

/** 与 {@link wrapLine} 逻辑一致，但整行（含行内 `<u>`）只包一层 `<p>`，避免块级段落把下划线从单词中拆开。 */
function wrapLineStem(line: string): string {
  const trimmed = line.trim();
  if (!trimmed) return "";
  const html = stemLineToInlineHtml(trimmed);
  const plain = stemPlainForWrapClass(trimmed);
  if (/^\d+[.、．)]\s/.test(plain)) {
    return `<p class="analysis-step">${html}</p>`;
  }
  if (/^[-•·]\s/.test(plain)) {
    return `<p class="analysis-bullet">${html}</p>`;
  }
  if (/^【.+】/.test(plain) || /^（\d+）/.test(plain)) {
    return `<p class="analysis-label">${html}</p>`;
  }
  return `<p>${html}</p>`;
}

/**
 * 题干展示：与 {@link formatAnalysisHtml} 相同的分段 / 行首样式规则，并保留 OCR/手写的 `<u>…</u>` 下划线（仅标签内文转义）。
 */
export function formatStemDisplayHtml(text: string): string {
  const raw = text ?? "";
  if (!raw.trim()) return "";

  const paragraphs = raw.split(/\n{2,}/);
  return paragraphs
    .map((block) => {
      const lines = block.split("\n").map((l) => l.trimEnd());
      const hasMultiline = lines.filter((l) => l.trim()).length > 1;
      if (!hasMultiline) {
        const line = lines.join("\n").trim();
        return line ? wrapLineStem(line) : "";
      }
      return lines.map((line) => (line.trim() ? wrapLineStem(line) : "")).join("");
    })
    .filter(Boolean)
    .join("");
}
