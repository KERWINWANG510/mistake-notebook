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
