/** 与 backend/app/services/vision_messages.py 保持一致的识图模型能力判断 */

const VISION_CAPABLE_HINTS = [
  '-vl',
  'vl-',
  '/vl',
  'vision',
  'ocr',
  'qwen-vl',
  'qvq',
  'glm-4v',
  'gpt-4o',
  'gpt-4.1',
  'gpt-4-vision',
  'kimi-k2',
  'qwen3.6',
  'qwen3.5',
  'qwen3-vl',
  'qwen2.5-vl',
  'qwen2-vl',
] as const;

const TEXT_ONLY_PREFIXES = [
  'qwen-turbo',
  'qwen-plus',
  'qwen-max',
  'qwen-long',
  'deepseek-chat',
  'deepseek-coder',
  'deepseek-reasoner',
  'moonshot-v1',
  'gpt-3.5',
] as const;

function norm(model: string): string {
  return model.trim().toLowerCase();
}

function hasVisionNameHint(m: string): boolean {
  if (m.includes('kimi') && ['k2', '2.5', '2.6', 'k2.5'].some((h) => m.includes(h))) {
    return true;
  }
  return VISION_CAPABLE_HINTS.some((h) => m.includes(h));
}

export function isKnownTextOnlyModel(model: string | null | undefined): boolean {
  const m = norm(model ?? '');
  if (!m || hasVisionNameHint(m)) return false;
  return TEXT_ONLY_PREFIXES.some(
    (p) => m === p || m.startsWith(`${p}-`) || m.startsWith(`${p}.`),
  );
}

export function isLikelyVisionCapableModel(model: string | null | undefined): boolean {
  const m = norm(model ?? '');
  if (!m || isKnownTextOnlyModel(m)) return false;
  return hasVisionNameHint(m);
}

export function effectiveVisionModel(
  selectedVision: string | null | undefined,
  selectedDefault: string | null | undefined,
): string | null {
  const v = (selectedVision ?? '').trim();
  if (v) return v;
  const d = (selectedDefault ?? '').trim();
  return d || null;
}

/** 不可用于 OCR 时返回错误文案，否则 null */
export function visionModelOcrError(model: string | null | undefined): string | null {
  const m = (model ?? '').trim();
  if (!m || !isKnownTextOnlyModel(m)) return null;
  return (
    `模型「${m}」为纯文本模型，不支持图片/OCR 识图。` +
    '请选择视觉模型（如 qwen-vl-plus、qwen-vl-ocr-latest、qwen3.6-plus、kimi-k2.5 等）'
  );
}

/** 能力不明确时的提示（不阻止保存） */
export function visionModelOcrWarning(model: string | null | undefined): string | null {
  const m = (model ?? '').trim();
  if (!m || visionModelOcrError(m)) return null;
  if (isLikelyVisionCapableModel(m)) return null;
  return `模型「${m}」可能不支持图片识图，若识别失败请改用 qwen-vl-* 或 qwen3.6-plus 等视觉模型`;
}

export function validateEffectiveVisionSelection(
  selectedVision: string | null | undefined,
  selectedDefault: string | null | undefined,
): { ok: boolean; error: string | null; warning: string | null; effective: string | null } {
  const effective = effectiveVisionModel(selectedVision, selectedDefault);
  if (!effective) {
    return { ok: true, error: null, warning: null, effective: null };
  }
  const error = visionModelOcrError(effective);
  if (error) {
    return { ok: false, error, warning: null, effective };
  }
  return {
    ok: true,
    error: null,
    warning: visionModelOcrWarning(effective),
    effective,
  };
}

export type VisionSelectOption = {
  label: string;
  value: string;
  disabled?: boolean;
};

export function mapVisionModelSelectOptions(
  items: { label: string; value: string }[],
): VisionSelectOption[] {
  return items.map((item) => {
    const id = item.value;
    if (isKnownTextOnlyModel(id)) {
      return { label: `${id}（不支持 OCR 识图）`, value: id, disabled: true };
    }
    if (!isLikelyVisionCapableModel(id)) {
      return { label: `${id}（可能不支持识图）`, value: id };
    }
    return { label: id, value: id };
  });
}
