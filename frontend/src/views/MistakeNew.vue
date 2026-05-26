<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NDynamicTags,
  NFormItem,
  NGrid,
  NGridItem,
  NImage,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NSpin,
  NTag,
  NText,
  useMessage,
} from "naive-ui";
import type { Subject, Grade } from "../api/client";
import {
  analyzeImageStream,
  createMistake,
  fetchGrades,
  fetchSubjects,
  solveFromStem,
  type AnalyzeStreamEvent,
  type AnalyzeStreamPhase,
} from "../api/client";
import AnalysisField from "../components/AnalysisField.vue";
import { ERROR_REASON_OPTIONS } from "../constants/errorReasons";
import { MISTAKE_SOURCE_OPTIONS } from "../constants/mistakeSources";

const router = useRouter();
const message = useMessage();

const subjects = ref<Subject[]>([]);
const grades = ref<Grade[]>([]);
const loadingMeta = ref(true);
const analyzing = ref(false);
const solvingStem = ref(false);
const saving = ref(false);
const hasRecognized = ref(false);
const showReanalyzeModal = ref(false);
const reanalyzeHint = ref("");

/** 流式识别：上游原始输出（便于感知进度） */
const analyzeStreamOcr = ref("");
const analyzeStreamSolve = ref("");
const analyzePhaseLabel = ref("");
const analyzeModels = ref<{ ocr: string; layout: string; solve: string } | null>(null);
const analyzeActivePhase = ref<AnalyzeStreamPhase | null>(null);
const analyzeCompletedPhases = ref<AnalyzeStreamPhase[]>([]);
const analyzeAbortCtrl = ref<AbortController | null>(null);

const ANALYZE_STEP_META: { phase: AnalyzeStreamPhase; title: string }[] = [
  { phase: "ocr", title: "识图" },
  { phase: "layout", title: "题干排版" },
  { phase: "solve", title: "生成解析与答案" },
];

function resetAnalyzeProgress() {
  analyzeStreamOcr.value = "";
  analyzeStreamSolve.value = "";
  analyzePhaseLabel.value = "准备识别…";
  analyzeModels.value = null;
  analyzeActivePhase.value = null;
  analyzeCompletedPhases.value = [];
}

function formatAnalyzePhaseDesc(label: string, model?: string) {
  const m = model?.trim();
  return m ? `${label}（${m}）` : label;
}

function analyzeStepStatus(phase: AnalyzeStreamPhase): "pending" | "active" | "done" {
  if (analyzeActivePhase.value === phase) return "active";
  if (analyzeCompletedPhases.value.includes(phase)) return "done";
  return "pending";
}

const analyzeStepRows = computed(() =>
  ANALYZE_STEP_META.map((meta) => ({
    ...meta,
    status: analyzeStepStatus(meta.phase),
    model: analyzeModels.value?.[meta.phase === "ocr" ? "ocr" : meta.phase === "layout" ? "layout" : "solve"] ?? "",
  })),
);

function markAnalyzePhaseComplete(phase: AnalyzeStreamPhase) {
  if (!analyzeCompletedPhases.value.includes(phase)) {
    analyzeCompletedPhases.value = [...analyzeCompletedPhases.value, phase];
  }
}

function onAnalyzeStreamEvent(ev: AnalyzeStreamEvent) {
  if (ev.type === "models") {
    analyzeModels.value = {
      ocr: ev.ocr_model,
      layout: ev.layout_model,
      solve: ev.solve_model,
    };
    return;
  }
  if (ev.type === "phase") {
    if (analyzeActivePhase.value) {
      markAnalyzePhaseComplete(analyzeActivePhase.value);
    }
    analyzeActivePhase.value = ev.phase;
    analyzePhaseLabel.value = formatAnalyzePhaseDesc(ev.label, ev.model);
    if (analyzeModels.value) {
      const key = ev.phase === "ocr" ? "ocr" : ev.phase === "layout" ? "layout" : "solve";
      analyzeModels.value = { ...analyzeModels.value, [key]: ev.model };
    }
    return;
  }
  if (ev.type === "delta") {
    if (ev.phase === "ocr") analyzeStreamOcr.value += ev.text;
    else analyzeStreamSolve.value += ev.text;
    return;
  }
  if (ev.type === "stem") {
    if (analyzeActivePhase.value === "layout") {
      markAnalyzePhaseComplete("layout");
    }
    stem.value = ev.text;
  }
}
const streamOcrPreRef = ref<HTMLElement | null>(null);
const streamSolvePreRef = ref<HTMLElement | null>(null);

watch([analyzeStreamOcr, analyzeStreamSolve], () => {
  if (!analyzing.value) return;
  void nextTick(() => {
    const a = streamOcrPreRef.value;
    const b = streamSolvePreRef.value;
    if (a) a.scrollTop = a.scrollHeight;
    if (b) b.scrollTop = b.scrollHeight;
  });
});

const originalFile = ref<File | null>(null);
const fileName = ref("");
/** 框选确认后用于识别与保存的文件 */
const uploadFile = ref<File | null>(null);
/** 主页面回显：确认后的题目图 */
const resultPreviewUrl = ref<string | null>(null);
const usedCropRegion = ref(false);

const showCropModal = ref(false);
const previewUrl = ref<string | null>(null);
const imgRef = ref<HTMLImageElement | null>(null);
const imgLoaded = ref(false);
const cropConfirming = ref(false);
/** 已有确认图后再次打开框选弹窗；取消时不应清空已确认的题目图 */
const cropReentry = ref(false);

const selRect = ref<{ x: number; y: number; w: number; h: number } | null>(null);
const dragStart = ref<{ x: number; y: number } | null>(null);
const dragBaseRect = ref<{ x: number; y: number; w: number; h: number } | null>(null);
const dragging = ref(false);
type CropInteraction = "draw" | "move" | "resize";
type ResizeHandle = "nw" | "n" | "ne" | "e" | "se" | "s" | "sw" | "w";
const cropInteraction = ref<CropInteraction | null>(null);
const activeHandle = ref<ResizeHandle | null>(null);
const resizeHandles: ResizeHandle[] = ["nw", "n", "ne", "e", "se", "s", "sw", "w"];

const zoomScale = ref(1);
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 4;
const ZOOM_STEP = 0.15;

const stem = ref("");
const analysis = ref("");
const answer = ref("");
const subjectId = ref<string | null>(null);
const gradeLevelId = ref<string | null>(null);
const knowledgeTags = ref<string[]>([]);
const errorReason = ref<string | null>(null);
const mistakeSource = ref<string | null>(null);

const errorReasonOptions = ERROR_REASON_OPTIONS.map((o) => ({ label: o.label, value: o.value }));
const mistakeSourceOptions = MISTAKE_SOURCE_OPTIONS.map((o) => ({ label: o.label, value: o.value }));

const fileInputRef = ref<HTMLInputElement | null>(null);

const narrow = ref(false);
function updateNarrow() {
  narrow.value = window.matchMedia("(max-width: 768px)").matches;
}
const gridXGap = computed(() => (narrow.value ? 0 : 16));
const gridYGap = computed(() => (narrow.value ? 10 : 16));
const stemFieldMinRows = computed(() => (narrow.value ? 3 : 4));
const stemFieldMaxRows = computed(() => (narrow.value ? 10 : 14));
const analysisFieldMinRows = computed(() => (narrow.value ? 4 : 6));

function pickAnotherImage() {
  fileInputRef.value?.click();
}

const MIN_SEL = 12;

function revokeResultPreview() {
  if (resultPreviewUrl.value) {
    URL.revokeObjectURL(resultPreviewUrl.value);
    resultPreviewUrl.value = null;
  }
}

function revokePreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
    previewUrl.value = null;
  }
}

function resetImageState() {
  revokePreview();
  revokeResultPreview();
  originalFile.value = null;
  uploadFile.value = null;
  fileName.value = "";
  usedCropRegion.value = false;
  selRect.value = null;
  imgLoaded.value = false;
}

/** 从拖拽数据中取第一张图片文件 */
function pickFirstImageFile(dt: DataTransfer | null): File | null {
  if (!dt) return null;
  const list = dt.files;
  if (list?.length) {
    for (let i = 0; i < list.length; i++) {
      const file = list[i];
      if (file.type.startsWith("image/")) return file;
    }
  }
  const items = dt.items;
  if (items?.length) {
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      if (it.kind === "file") {
        const file = it.getAsFile();
        if (file?.type.startsWith("image/")) return file;
      }
    }
  }
  return null;
}

const imageDropActive = ref(false);

function onImageDragOver(e: DragEvent) {
  e.preventDefault();
  if (e.dataTransfer) {
    e.dataTransfer.dropEffect = analyzeBusy.value ? "none" : "copy";
  }
}

function onImageDragEnter(e: DragEvent) {
  if (analyzeBusy.value) return;
  e.preventDefault();
  imageDropActive.value = true;
}

function onImageDragLeave(e: DragEvent) {
  const root = e.currentTarget as HTMLElement;
  const rel = e.relatedTarget as Node | null;
  if (rel && root.contains(rel)) return;
  imageDropActive.value = false;
}

function onImageDrop(e: DragEvent) {
  e.preventDefault();
  imageDropActive.value = false;
  if (analyzeBusy.value) {
    message.warning("请等待当前识别完成后再更换图片");
    return;
  }
  const f = pickFirstImageFile(e.dataTransfer);
  if (!f) {
    message.warning("请拖拽图片文件（如 JPG、PNG）到此处");
    return;
  }
  acceptImageFile(f);
}

function acceptImageFile(f: File) {
  if (!f.type.startsWith("image/")) {
    message.warning("请选择图片文件（如 JPG、PNG、WebP）");
    return;
  }
  cropReentry.value = false;
  revokePreview();
  revokeResultPreview();
  selRect.value = null;
  imgLoaded.value = false;
  uploadFile.value = null;
  usedCropRegion.value = false;
  stem.value = "";
  analysis.value = "";
  answer.value = "";
  subjectId.value = null;
  gradeLevelId.value = null;
  knowledgeTags.value = [];
  errorReason.value = null;
  mistakeSource.value = null;
  hasRecognized.value = false;
  originalFile.value = f;
  fileName.value = f.name;
  previewUrl.value = URL.createObjectURL(f);
  resetZoom();
  showCropModal.value = true;
}

function onPickFile(e: Event) {
  const input = e.target as HTMLInputElement;
  const f = input.files?.[0] ?? null;
  input.value = "";
  if (!f) return;
  acceptImageFile(f);
}

function onImgLoad() {
  imgLoaded.value = true;
}

function getPointInImageFromEvent(e: MouseEvent | TouchEvent, img: HTMLImageElement): { x: number; y: number } {
  const r = img.getBoundingClientRect();
  const scale = zoomScale.value || 1;
  let cx: number;
  let cy: number;
  if ("touches" in e && e.touches.length > 0) {
    cx = e.touches[0].clientX;
    cy = e.touches[0].clientY;
  } else if ("changedTouches" in e && e.changedTouches.length > 0) {
    cx = e.changedTouches[0].clientX;
    cy = e.changedTouches[0].clientY;
  } else {
    cx = (e as MouseEvent).clientX;
    cy = (e as MouseEvent).clientY;
  }
  // 选区坐标存于未缩放布局空间，避免父级 scale 导致双重缩放错位
  return { x: (cx - r.left) / scale, y: (cy - r.top) / scale };
}

function getImageDisplaySize() {
  const img = imgRef.value;
  if (!img) return { w: 0, h: 0 };
  const w = img.offsetWidth;
  const h = img.offsetHeight;
  if (w > 0 && h > 0) return { w, h };
  const scale = zoomScale.value || 1;
  const r = img.getBoundingClientRect();
  return { w: r.width / scale, h: r.height / scale };
}

function resetZoom() {
  zoomScale.value = 1;
}

function zoomIn() {
  zoomScale.value = clamp(zoomScale.value + ZOOM_STEP, MIN_ZOOM, MAX_ZOOM);
}

function zoomOut() {
  zoomScale.value = clamp(zoomScale.value - ZOOM_STEP, MIN_ZOOM, MAX_ZOOM);
}

function onCropWheel(e: WheelEvent) {
  e.preventDefault();
  if (e.deltaY < 0) zoomIn();
  else zoomOut();
}

function clampRectToImage(rect: { x: number; y: number; w: number; h: number }) {
  const { w: iw, h: ih } = getImageDisplaySize();
  if (iw <= 0 || ih <= 0) return rect;
  let { x, y, w, h } = rect;
  w = Math.max(MIN_SEL, w);
  h = Math.max(MIN_SEL, h);
  if (w > iw) w = iw;
  if (h > ih) h = ih;
  x = clamp(x, 0, iw - w);
  y = clamp(y, 0, ih - h);
  return { x, y, w, h };
}

function attachCropListeners() {
  window.addEventListener("mousemove", onCropPointerMove);
  window.addEventListener("mouseup", onCropPointerUp);
  window.addEventListener("touchmove", onCropPointerMove, { passive: false });
  window.addEventListener("touchend", onCropPointerUp);
}

function detachCropListeners() {
  window.removeEventListener("mousemove", onCropPointerMove);
  window.removeEventListener("mouseup", onCropPointerUp);
  window.removeEventListener("touchmove", onCropPointerMove);
  window.removeEventListener("touchend", onCropPointerUp);
}

function beginCropInteraction(
  mode: CropInteraction,
  e: MouseEvent | TouchEvent,
  handle: ResizeHandle | null = null,
) {
  if (!imgRef.value) return;
  if ("touches" in e) e.preventDefault();
  const p = getPointInImageFromEvent(e, imgRef.value);
  cropInteraction.value = mode;
  activeHandle.value = handle;
  dragStart.value = p;
  dragBaseRect.value = selRect.value ? { ...selRect.value } : null;
  dragging.value = true;
  attachCropListeners();
}

function onCropPointerDown(e: MouseEvent | TouchEvent) {
  if (!imgRef.value || !previewUrl.value) return;
  if ("touches" in e) e.preventDefault();
  beginCropInteraction("draw", e);
  const p = getPointInImageFromEvent(e, imgRef.value);
  selRect.value = { x: p.x, y: p.y, w: 0, h: 0 };
}

function onSelectionMoveStart(e: MouseEvent | TouchEvent) {
  if (!selRect.value) return;
  beginCropInteraction("move", e);
}

function onHandlePointerDown(handle: ResizeHandle, e: MouseEvent | TouchEvent) {
  if (!selRect.value) return;
  beginCropInteraction("resize", e, handle);
}

function applyResize(handle: ResizeHandle, base: { x: number; y: number; w: number; h: number }, dx: number, dy: number) {
  let { x, y, w, h } = base;
  switch (handle) {
    case "nw":
      x += dx;
      w -= dx;
      y += dy;
      h -= dy;
      break;
    case "n":
      y += dy;
      h -= dy;
      break;
    case "ne":
      w += dx;
      y += dy;
      h -= dy;
      break;
    case "e":
      w += dx;
      break;
    case "se":
      w += dx;
      h += dy;
      break;
    case "s":
      h += dy;
      break;
    case "sw":
      x += dx;
      w -= dx;
      h += dy;
      break;
    case "w":
      x += dx;
      w -= dx;
      break;
  }
  if (w < 0) {
    x += w;
    w = -w;
  }
  if (h < 0) {
    y += h;
    h = -h;
  }
  return clampRectToImage({ x, y, w, h });
}

function onCropPointerMove(e: MouseEvent | TouchEvent) {
  if (!dragging.value || !dragStart.value || !imgRef.value || !cropInteraction.value) return;
  if ("touches" in e) e.preventDefault();
  const p = getPointInImageFromEvent(e, imgRef.value);
  const dx = p.x - dragStart.value.x;
  const dy = p.y - dragStart.value.y;

  if (cropInteraction.value === "draw") {
    const x0 = dragStart.value.x;
    const y0 = dragStart.value.y;
    selRect.value = clampRectToImage({
      x: Math.min(x0, p.x),
      y: Math.min(y0, p.y),
      w: Math.abs(p.x - x0),
      h: Math.abs(p.y - y0),
    });
    return;
  }

  const base = dragBaseRect.value;
  if (!base) return;

  if (cropInteraction.value === "move") {
    selRect.value = clampRectToImage({ ...base, x: base.x + dx, y: base.y + dy });
    return;
  }

  if (cropInteraction.value === "resize" && activeHandle.value) {
    selRect.value = applyResize(activeHandle.value, base, dx, dy);
  }
}

function onCropPointerUp() {
  dragging.value = false;
  dragStart.value = null;
  dragBaseRect.value = null;
  cropInteraction.value = null;
  activeHandle.value = null;
  detachCropListeners();
  const r = selRect.value;
  if (r && (r.w < MIN_SEL || r.h < MIN_SEL)) {
    selRect.value = null;
  }
}

function clearSelection() {
  selRect.value = null;
}

function clamp(n: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, n));
}

async function buildCroppedFile(): Promise<File | null> {
  const raw = originalFile.value;
  if (!raw) return null;
  const img = imgRef.value;
  const rect = selRect.value;
  if (!img || !imgLoaded.value || !rect || rect.w < MIN_SEL || rect.h < MIN_SEL) {
    return raw;
  }
  const nw = img.naturalWidth;
  const nh = img.naturalHeight;
  const { w: rw, h: rh } = getImageDisplaySize();
  if (rw <= 0 || rh <= 0 || nw <= 0 || nh <= 0) return raw;

  let sx = (rect.x / rw) * nw;
  let sy = (rect.y / rh) * nh;
  let sw = (rect.w / rw) * nw;
  let sh = (rect.h / rh) * nh;
  sx = clamp(sx, 0, nw - 1);
  sy = clamp(sy, 0, nh - 1);
  sw = clamp(sw, 1, nw - sx);
  sh = clamp(sh, 1, nh - sy);
  sx = Math.round(sx);
  sy = Math.round(sy);
  sw = Math.round(sw);
  sh = Math.round(sh);

  const canvas = document.createElement("canvas");
  canvas.width = sw;
  canvas.height = sh;
  const ctx = canvas.getContext("2d");
  if (!ctx) return raw;
  ctx.drawImage(img, sx, sy, sw, sh, 0, 0, sw, sh);

  const mime = raw.type && raw.type.startsWith("image/") ? raw.type : "image/png";
  const quality = mime === "image/jpeg" || mime === "image/webp" ? 0.92 : undefined;
  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob((b) => resolve(b), mime, quality as number | undefined);
  });
  if (!blob) return raw;
  const base = (fileName.value || "question").replace(/\.[^.]+$/, "");
  const ext = mime === "image/jpeg" ? "jpg" : mime === "image/webp" ? "webp" : "png";
  return new File([blob], `${base}-crop.${ext}`, { type: mime });
}

function setResultPreviewFromFile(file: File) {
  revokeResultPreview();
  resultPreviewUrl.value = URL.createObjectURL(file);
}

function onCropModalShowUpdate(show: boolean) {
  if (show) return;
  if (cropConfirming.value) {
    cropConfirming.value = false;
    return;
  }
  cancelCrop();
}

async function confirmCrop(useFull: boolean) {
  if (!originalFile.value) return;
  if (!imgLoaded.value) {
    message.warning("请等待图片加载完成");
    return;
  }
  cropConfirming.value = true;
  if (useFull) {
    uploadFile.value = originalFile.value;
    usedCropRegion.value = false;
  } else {
    const rect = selRect.value;
    if (!rect || rect.w < MIN_SEL || rect.h < MIN_SEL) {
      message.warning("请先在图上拖拽框选题目区域，或点击「使用整张图」");
      cropConfirming.value = false;
      return;
    }
    uploadFile.value = (await buildCroppedFile()) ?? originalFile.value;
    usedCropRegion.value = true;
  }
  setResultPreviewFromFile(uploadFile.value);
  cropReentry.value = false;
  showCropModal.value = false;
  await runAnalyze();
}

function cancelCrop() {
  showCropModal.value = false;
  selRect.value = null;
  resetZoom();
  imgLoaded.value = false;
  if (cropReentry.value) {
    cropReentry.value = false;
    return;
  }
  resetImageState();
}

function reopenCropModal() {
  if (!originalFile.value || !previewUrl.value) return;
  cropReentry.value = true;
  selRect.value = null;
  resetZoom();
  showCropModal.value = true;
}

onMounted(async () => {
  updateNarrow();
  window.addEventListener("resize", updateNarrow);
  try {
    grades.value = await fetchGrades();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loadingMeta.value = false;
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", updateNarrow);
  analyzeAbortCtrl.value?.abort();
  detachCropListeners();
  revokePreview();
  revokeResultPreview();
});

const subjectOptions = computed(() => subjects.value.map((s) => ({ label: s.name, value: s.id })));
const gradeOptions = computed(() => grades.value.map((g) => ({ label: g.name, value: g.id })));

async function loadSubjectsForGrade(gradeId: string | null) {
  if (!gradeId) {
    subjects.value = [];
    subjectId.value = null;
    return;
  }
  try {
    subjects.value = await fetchSubjects({ grade_level_id: gradeId });
    if (subjectId.value && !subjects.value.some((s) => s.id === subjectId.value)) {
      subjectId.value = null;
    }
  } catch (e) {
    message.error((e as Error).message);
    subjects.value = [];
  }
}

const selectionStyle = computed(() => {
  const r = selRect.value;
  if (!r) return { display: "none" };
  return {
    display: "block",
    left: `${r.x}px`,
    top: `${r.y}px`,
    width: `${r.w}px`,
    height: `${r.h}px`,
  };
});

const cropStageStyle = computed(() => ({
  transform: `scale(${zoomScale.value})`,
  transformOrigin: "0 0",
}));

const zoomPercent = computed(() => Math.round(zoomScale.value * 100));

const analyzeBusy = computed(() => analyzing.value || solvingStem.value);
const analyzeSpinDesc = computed(() => {
  if (solvingStem.value) return "正在根据题干生成解析…";
  if (analyzing.value && analyzePhaseLabel.value) return analyzePhaseLabel.value;
  return "AI 识别中…";
});

async function applySolveSuggestions(
  res: {
    analysis: string;
    answer: string;
    suggested_subject_code: string | null;
    suggested_grade_level: number | null;
    knowledge_tags?: string[];
  },
  opts?: { fallbackSubject?: boolean },
) {
  analysis.value = res.analysis;
  answer.value = res.answer;
  if (res.suggested_grade_level != null) {
    const g = grades.value.find((x) => x.level === res.suggested_grade_level);
    if (g) {
      gradeLevelId.value = g.id;
      await loadSubjectsForGrade(g.id);
    }
  }
  const subj = subjects.value.find((s) => s.code === res.suggested_subject_code);
  if (subj) {
    subjectId.value = subj.id;
  } else if (opts?.fallbackSubject) {
    subjectId.value = subjects.value[0]?.id ?? null;
  }
  if (res.knowledge_tags?.length) {
    knowledgeTags.value = [...res.knowledge_tags];
  }
}

function solveContext() {
  const subj = subjects.value.find((s) => s.id === subjectId.value);
  const grade = grades.value.find((g) => g.id === gradeLevelId.value);
  return {
    subject_code: subj?.code ?? null,
    grade_level: grade?.level ?? null,
  };
}

async function runAnalyze(ocrHint?: string) {
  if (!uploadFile.value) {
    message.warning("请先选择题目图片并完成框选确认");
    return;
  }
  analyzeAbortCtrl.value?.abort();
  analyzeAbortCtrl.value = new AbortController();
  analyzing.value = true;
  resetAnalyzeProgress();
  try {
    const hint = ocrHint?.trim();
    const res = await analyzeImageStream(
      uploadFile.value,
      (ev) => onAnalyzeStreamEvent(ev),
      hint ? { ocr_hint: hint } : undefined,
      analyzeAbortCtrl.value.signal,
    );
    stem.value = res.stem;
    markAnalyzePhaseComplete("ocr");
    markAnalyzePhaseComplete("layout");
    markAnalyzePhaseComplete("solve");
    analyzeActivePhase.value = null;
    await applySolveSuggestions(res, { fallbackSubject: true });
    hasRecognized.value = true;
    message.success(usedCropRegion.value ? "已按框选区域识别，请核对题干并保存" : "识别完成，请核对题干并保存");
  } catch (e) {
    const err = e as Error;
    if (err.name === "AbortError") return;
    message.error(err.message);
  } finally {
    analyzing.value = false;
    analyzePhaseLabel.value = "";
    analyzeModels.value = null;
    analyzeActivePhase.value = null;
    analyzeCompletedPhases.value = [];
    analyzeAbortCtrl.value = null;
  }
}

function openReanalyzeModal() {
  if (!uploadFile.value) {
    message.warning("请先选择题目图片并完成框选确认");
    return;
  }
  if (analyzeBusy.value) return;
  reanalyzeHint.value = "";
  showReanalyzeModal.value = true;
}

function cancelReanalyze() {
  showReanalyzeModal.value = false;
}

async function confirmReanalyze() {
  showReanalyzeModal.value = false;
  await runAnalyze(reanalyzeHint.value);
}

async function runSolveFromStem() {
  const text = stem.value.trim();
  if (!text) {
    message.warning("请先填写题干");
    return;
  }
  solvingStem.value = true;
  try {
    const res = await solveFromStem(text, solveContext());
    await applySolveSuggestions(res);
    message.success("已根据题干重新生成解析与答案");
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    solvingStem.value = false;
  }
}

async function save() {
  if (!subjectId.value || !gradeLevelId.value) {
    message.warning("请选择科目与年级");
    return;
  }
  if (!stem.value.trim()) {
    message.warning("题干不能为空");
    return;
  }
  if (!errorReason.value) {
    message.warning("请选择错因");
    return;
  }
  if (!mistakeSource.value) {
    message.warning("请选择错题来源");
    return;
  }
  if (!uploadFile.value) {
    message.warning("请先选择题目图片并完成框选确认");
    return;
  }
  saving.value = true;
  try {
    await createMistake({
      subject_id: subjectId.value,
      grade_level_id: gradeLevelId.value,
      stem: stem.value,
      analysis: analysis.value,
      answer: answer.value,
      knowledge_tags: knowledgeTags.value,
      error_reason: errorReason.value,
      mistake_source: mistakeSource.value,
      image: uploadFile.value,
    });
    message.success("已保存");
    router.push("/mistakes");
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <NSpin :show="loadingMeta">
    <div class="mistake-new page-root" :class="{ 'page-root--fixed-actions': narrow }">
      <header class="page-header mistake-new__header">
        <h1 class="page-header__title">录入错题</h1>
        <p class="page-header__desc mistake-new__header-desc">
          上传并框选题目后自动识别；识别过程采用流式输出。题干与解题思路均支持「编辑 / 排版预览」（**加粗**、分段、&lt;u&gt; 下划线等）。可修改题干后重新生成解析与答案。
        </p>
        <p v-if="narrow" class="mistake-new__header-mobile-tip">上传题目图 → 框选识别 → 核对后保存</p>
      </header>
      <NCard class="surface-card mistake-new__card" size="small" :bordered="false">
        <Teleport to="body">
          <div
            v-if="analyzeBusy"
            class="mistake-new__busy-overlay"
            role="status"
            aria-live="polite"
            :aria-label="analyzeSpinDesc || '正在处理'"
          >
            <NSpin :show="true" :description="analyzeSpinDesc" />
          </div>
        </Teleport>
        <div class="mistake-new__card-shell" :class="{ 'mistake-new__card-shell--busy': analyzeBusy }">
          <input
            id="mistake-image-input"
            ref="fileInputRef"
            type="file"
            accept="image/*"
            class="hidden-file-input"
            @change="onPickFile"
          />

          <NGrid
            class="mistake-new__grid"
            :cols="24"
            :x-gap="gridXGap"
            :y-gap="gridYGap"
            item-responsive
            responsive="screen"
          >
            <NGridItem class="mistake-new__aside" span="24 l:9">
              <section class="mistake-new__section mistake-new__panel">
                <h2 class="mistake-new__section-title">题目图片</h2>
                <label
                  v-if="!resultPreviewUrl"
                  class="file-picker file-picker--compact"
                  :class="{ 'file-picker--dragover': imageDropActive }"
                  for="mistake-image-input"
                  @dragenter.prevent="onImageDragEnter"
                  @dragover.prevent="onImageDragOver"
                  @dragleave.prevent="onImageDragLeave"
                  @drop.prevent="onImageDrop"
                >
                  <div class="file-picker__text">
                    <div class="file-picker__hint">点击选择或拖拽题目图片</div>
                    <div class="file-picker__sub">上传后将在弹窗中框选识别区域</div>
                  </div>
                </label>
                <div
                  v-else
                  class="result-preview result-preview--compact"
                  :class="{ 'result-preview--dragover': imageDropActive }"
                  @dragenter.prevent="onImageDragEnter"
                  @dragover.prevent="onImageDragOver"
                  @dragleave.prevent="onImageDragLeave"
                  @drop.prevent="onImageDrop"
                >
                  <NImage
                    width="100%"
                    class="result-preview__image"
                    :src="resultPreviewUrl"
                    object-fit="contain"
                    alt="已确认的题目区域"
                    :previewed-img-props="{ style: { maxWidth: 'none', maxHeight: 'none' } }"
                  />
                  <p class="result-preview__zoom-hint">点击图片可查看原尺寸；也可拖拽新图片到此处更换</p>
                  <div class="result-preview__actions app-actions">
                    <NTag v-if="usedCropRegion" size="small" type="info" :bordered="false">已框选</NTag>
                    <NTag v-else size="small" :bordered="false">整张图</NTag>
                    <NButton size="tiny" tertiary @click="reopenCropModal">重新框选</NButton>
                    <NButton
                      size="tiny"
                      secondary
                      :loading="analyzing"
                      :disabled="analyzeBusy || !uploadFile"
                      @click="openReanalyzeModal"
                    >
                      重新识别
                    </NButton>
                    <NButton size="tiny" quaternary @click="pickAnotherImage">更换图片</NButton>
                  </div>
                </div>
              </section>

              <section class="mistake-new__section mistake-new__panel">
                <h2 class="mistake-new__section-title">分类信息</h2>
                <div class="mistake-new__meta-grid">
                  <NFormItem label="年级" :show-feedback="false" class="mistake-new__item" label-placement="top">
                    <NSelect
                      v-model:value="gradeLevelId"
                      size="small"
                      :options="gradeOptions"
                      placeholder="请先选择年级"
                      @update:value="(v) => void loadSubjectsForGrade(v)"
                    />
                  </NFormItem>
                  <NFormItem label="科目" :show-feedback="false" class="mistake-new__item" label-placement="top">
                    <NSelect
                      v-model:value="subjectId"
                      size="small"
                      :options="subjectOptions"
                      :disabled="!gradeLevelId"
                      placeholder="请选择科目"
                    />
                  </NFormItem>
                  <NFormItem label="错因" :show-feedback="false" class="mistake-new__item" label-placement="top">
                    <NSelect
                      v-model:value="errorReason"
                      size="small"
                      :options="errorReasonOptions"
                      placeholder="请选择错因"
                      clearable
                    />
                  </NFormItem>
                  <NFormItem label="错题来源" :show-feedback="false" class="mistake-new__item" label-placement="top">
                    <NSelect
                      v-model:value="mistakeSource"
                      size="small"
                      :options="mistakeSourceOptions"
                      placeholder="请选择来源"
                      clearable
                    />
                  </NFormItem>
                  <NFormItem
                    label="知识点标签"
                    :show-feedback="false"
                    class="mistake-new__item mistake-new__item--full"
                    label-placement="top"
                  >
                    <NDynamicTags
                      v-model:value="knowledgeTags"
                      size="small"
                      :max="6"
                      placeholder="AI 识别后可编辑，回车添加"
                    />
                  </NFormItem>
                </div>
              </section>
            </NGridItem>

            <NGridItem span="24 l:15">
              <section class="mistake-new__section mistake-new__section--main mistake-new__panel">
                <div class="mistake-new__section-head">
                  <h2 class="mistake-new__section-title">题干与解答</h2>
                  <NText v-if="hasRecognized" depth="3" class="mistake-new__section-hint">修改题干后可重新生成</NText>
                </div>

                <div v-show="analyzing" class="mistake-new__stream-panel">
                  <NText depth="3" class="mistake-new__stream-tip mistake-new__stream-tip--desktop">
                    AI 实时输出（与聊天类似逐字返回；完成后将写入下方题干与解答）
                  </NText>
                  <NText depth="3" class="mistake-new__stream-tip mistake-new__stream-tip--mobile">
                    AI 识别中，完成后自动填入下方
                  </NText>
                  <ol v-if="analyzeModels" class="mistake-new__analyze-steps" aria-label="识别步骤与模型">
                    <li
                      v-for="step in analyzeStepRows"
                      :key="step.phase"
                      class="mistake-new__analyze-step"
                      :class="`mistake-new__analyze-step--${step.status}`"
                    >
                      <span class="mistake-new__analyze-step-title">{{ step.title }}</span>
                      <span class="mistake-new__analyze-step-model">{{ step.model || "—" }}</span>
                    </li>
                  </ol>
                  <div class="mistake-new__stream-columns">
                    <div class="mistake-new__stream-col">
                      <div class="mistake-new__stream-col-title">
                        识图输出
                        <span v-if="analyzeModels" class="mistake-new__stream-col-model">{{ analyzeModels.ocr }}</span>
                      </div>
                      <pre ref="streamOcrPreRef" class="mistake-new__stream-pre">{{ analyzeStreamOcr }}</pre>
                    </div>
                    <div class="mistake-new__stream-col">
                      <div class="mistake-new__stream-col-title">
                        解析输出
                        <span v-if="analyzeModels" class="mistake-new__stream-col-model">{{ analyzeModels.solve }}</span>
                      </div>
                      <pre ref="streamSolvePreRef" class="mistake-new__stream-pre">{{ analyzeStreamSolve }}</pre>
                    </div>
                  </div>
                </div>

                <NSpace vertical :size="narrow ? 8 : 12" style="width: 100%">
                  <NFormItem label="题干" :show-feedback="false" class="mistake-new__item" label-placement="top">
                    <NSpace vertical :size="8" style="width: 100%">
                      <AnalysisField
                        v-model="stem"
                        variant="stem"
                        :min-rows="stemFieldMinRows"
                        :max-rows="stemFieldMaxRows"
                        empty-text="识别结果将显示在此"
                      />
                      <NButton
                        v-if="hasRecognized"
                        size="small"
                        secondary
                        block
                        :loading="solvingStem"
                        :disabled="analyzeBusy || !stem.trim()"
                        @click="runSolveFromStem"
                      >
                        <span class="mistake-new__regen-label mistake-new__regen-label--full">根据题干重新生成解析与答案</span>
                        <span class="mistake-new__regen-label mistake-new__regen-label--short">重新生成解析</span>
                      </NButton>
                    </NSpace>
                  </NFormItem>

                  <NFormItem label="解题思路" :show-feedback="false" class="mistake-new__item" label-placement="top">
                    <AnalysisField
                      v-model="analysis"
                      :min-rows="analysisFieldMinRows"
                      empty-text="识别或根据题干生成后将显示解题思路"
                    />
                  </NFormItem>

                  <NFormItem label="答案" :show-feedback="false" class="mistake-new__item" label-placement="top">
                    <NInput
                      v-model:value="answer"
                      type="textarea"
                      size="small"
                      clearable
                      placeholder="最终答案"
                      :autosize="{ minRows: narrow ? 2 : 2, maxRows: narrow ? 6 : 10 }"
                    />
                  </NFormItem>
                </NSpace>
              </section>
            </NGridItem>
          </NGrid>

          <footer
            class="mistake-new__footer app-actions"
            :class="narrow ? 'mistake-new__footer--dock app-actions--fixed' : 'app-actions--bar'"
          >
            <div class="mistake-new__footer-inner app-actions--fixed-inner">
              <NButton size="small" @click="router.push('/mistakes')">返回</NButton>
              <NButton
                type="primary"
                size="small"
                :loading="saving"
                :disabled="analyzeBusy || !uploadFile"
                @click="save"
              >
                <span class="mistake-new__save-label mistake-new__save-label--full">保存到错题本</span>
                <span class="mistake-new__save-label mistake-new__save-label--short">保存</span>
              </NButton>
            </div>
          </footer>
        </div>
      </NCard>
    </div>

    <NModal
      v-model:show="showCropModal"
      preset="card"
      title="框选题目区域"
      class="crop-modal"
      style="width: min(680px, 96vw)"
      :mask-closable="false"
      @update:show="onCropModalShowUpdate"
    >
      <div class="crop-modal__intro">
        <NText depth="3" class="crop-modal__tip">拖拽框选；框内移动、边角调整大小；滚轮或按钮缩放。</NText>
        <NSpace align="center" :size="6" class="crop-zoom-bar">
          <NButton size="tiny" :disabled="zoomScale <= MIN_ZOOM" @click="zoomOut">−</NButton>
          <NText depth="2" class="crop-zoom-bar__label">{{ zoomPercent }}%</NText>
          <NButton size="tiny" :disabled="zoomScale >= MAX_ZOOM" @click="zoomIn">+</NButton>
          <NButton size="tiny" quaternary :disabled="zoomScale === 1" @click="resetZoom">重置</NButton>
        </NSpace>
      </div>
      <div v-if="previewUrl" class="crop-modal-body" @wheel.prevent="onCropWheel">
        <div class="crop-viewport">
          <div
            class="crop-stage"
            :style="cropStageStyle"
            @mousedown="onCropPointerDown"
            @touchstart="onCropPointerDown"
          >
            <img ref="imgRef" :src="previewUrl" alt="题目预览" draggable="false" @load="onImgLoad" />
            <div v-if="selRect" class="crop-selection" :style="selectionStyle">
              <div
                class="crop-selection__body"
                @mousedown.stop="onSelectionMoveStart"
                @touchstart.stop="onSelectionMoveStart"
              />
              <div
                v-for="handle in resizeHandles"
                :key="handle"
                class="crop-handle"
                :class="`crop-handle--${handle}`"
                @mousedown.stop.prevent="onHandlePointerDown(handle, $event)"
                @touchstart.stop.prevent="onHandlePointerDown(handle, $event)"
              />
            </div>
          </div>
        </div>
      </div>
      <NSpace justify="end" align="center" wrap :size="6" class="crop-modal__footer app-actions">
        <NButton size="tiny" secondary :disabled="!selRect" @click="clearSelection">清除选区</NButton>
        <NButton size="small" @click="cancelCrop">取消</NButton>
        <NButton size="small" :disabled="!imgLoaded" @click="confirmCrop(true)">整张图</NButton>
        <NButton type="primary" size="small" :disabled="!imgLoaded" @click="confirmCrop(false)">确定选区</NButton>
      </NSpace>
    </NModal>

    <NModal
      v-model:show="showReanalyzeModal"
      preset="card"
      title="重新识别题干"
      style="width: min(520px, 94vw)"
      :mask-closable="!analyzing"
    >
      <NText depth="3" class="reanalyze-modal__tip">
        可填写补充说明（如漏识别的选项、易错单词、下划线位置等），将一并传给识图模型以提高准确度；留空则仅按图片重新识别。
      </NText>
      <NInput
        v-model:value="reanalyzeHint"
        type="textarea"
        clearable
        :autosize="{ minRows: 6, maxRows: 14 }"
        placeholder="例如：第 2 题选项 B 是 boy 不是 toy；划线在字母 o 上…"
        class="reanalyze-modal__input"
      />
      <NSpace justify="end" align="center" wrap :size="8" class="reanalyze-modal__footer app-actions">
        <NButton size="small" :disabled="analyzing" @click="cancelReanalyze">取消</NButton>
        <NButton type="primary" size="small" :loading="analyzing" @click="confirmReanalyze">开始识别</NButton>
      </NSpace>
    </NModal>
  </NSpin>
</template>

<style scoped>
.mistake-new {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.mistake-new__card {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.mistake-new__busy-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);
  pointer-events: auto;
}

.mistake-new__busy-overlay :deep(.n-spin-body) {
  position: static;
  width: auto;
  height: auto;
}

.mistake-new__card-shell--busy {
  pointer-events: none;
  user-select: none;
}

.mistake-new__header {
  margin-bottom: 12px;
}

.mistake-new__header .page-header__title {
  font-size: 1.2rem;
  margin-bottom: 4px;
}

.mistake-new__header .page-header__desc {
  font-size: 13px;
}

.mistake-new__card :deep(.n-card__content) {
  padding: 16px 18px;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.mistake-new__grid {
  width: 100%;
  max-width: 100%;
  min-width: 0;
}

.mistake-new__grid :deep(.n-grid),
.mistake-new__grid :deep(.n-grid-item) {
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.mistake-new__aside,
.mistake-new__section,
.mistake-new__section--main {
  min-width: 0;
  max-width: 100%;
}

.mistake-new :deep(.analysis-field),
.mistake-new :deep(.formatted-analysis--panel),
.mistake-new :deep(.n-form-item),
.mistake-new :deep(.n-form-item-blank),
.mistake-new :deep(.n-input) {
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.mistake-new__aside {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (min-width: 1024px) {
  .mistake-new__aside {
    position: sticky;
    top: 8px;
    align-self: flex-start;
  }

  .mistake-new__section--main {
    padding-left: 4px;
    border-left: 1px solid var(--app-border);
    min-height: 100%;
  }
}

.mistake-new__section-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  letter-spacing: 0.02em;
}

.mistake-new__section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.mistake-new__section-head .mistake-new__section-title {
  margin-bottom: 0;
}

.mistake-new__section-hint {
  font-size: 12px;
}

.mistake-new__stream-panel {
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(99, 102, 241, 0.22);
  background: rgba(99, 102, 241, 0.04);
}

.mistake-new__stream-tip {
  display: block;
  margin-bottom: 8px;
  font-size: 12px;
  line-height: 1.45;
}

.mistake-new__stream-columns {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
}

.mistake-new__analyze-steps {
  list-style: none;
  margin: 0 0 10px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mistake-new__analyze-step {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid rgba(226, 232, 240, 0.95);
  background: rgba(255, 255, 255, 0.75);
  font-size: 12px;
  line-height: 1.4;
}

.mistake-new__analyze-step--active {
  border-color: rgba(99, 102, 241, 0.45);
  background: rgba(99, 102, 241, 0.08);
}

.mistake-new__analyze-step--done {
  opacity: 0.72;
}

.mistake-new__analyze-step-title {
  font-weight: 600;
  color: #334155;
  flex-shrink: 0;
}

.mistake-new__analyze-step-model {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  color: #6366f1;
  text-align: right;
  word-break: break-all;
}

.mistake-new__stream-col-title {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 4px;
}

.mistake-new__stream-col-model {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-weight: 500;
  font-size: 10px;
  color: #6366f1;
  word-break: break-all;
}

.mistake-new__stream-pre {
  margin: 0;
  min-height: 72px;
  max-height: min(28vh, 220px);
  overflow: auto;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(226, 232, 240, 0.95);
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
  color: #334155;
}

.mistake-new__stream-pre :deep(u) {
  display: inline;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.mistake-new__item {
  margin-bottom: 0;
}

.mistake-new__item :deep(.n-form-item-label) {
  padding-bottom: 4px;
  font-size: 13px;
  font-weight: 500;
}

.mistake-new__item :deep(.n-form-item-blank) {
  width: 100%;
  min-width: 0;
}

.mistake-new__item :deep(.n-input) {
  width: 100%;
}

.mistake-new__header-mobile-tip {
  display: none;
}

.mistake-new__meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 12px;
  width: 100%;
}

.mistake-new__meta-grid .mistake-new__item {
  min-width: 0;
}

.mistake-new__meta-grid .mistake-new__item--full {
  grid-column: 1 / -1;
}

.mistake-new__item--full {
  width: 100%;
}

.mistake-new__stream-tip--mobile {
  display: none;
}

.mistake-new__regen-label--short,
.mistake-new__save-label--short {
  display: none;
}

.mistake-new__footer-inner {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.mistake-new__panel {
  /* 桌面端不额外包一层卡片 */
}

@media (max-width: 768px) {
  .mistake-new__header {
    margin-bottom: 6px;
  }

  .mistake-new__header .page-header__title {
    font-size: 1.08rem;
    margin-bottom: 2px;
  }

  .mistake-new__header-desc {
    display: none;
  }

  .mistake-new__header-mobile-tip {
    display: block;
    margin: 0;
    font-size: 12px;
    line-height: 1.4;
    color: var(--app-text-muted, #64748b);
  }

  .mistake-new__card {
    background: transparent !important;
    box-shadow: none !important;
  }

  .mistake-new__card :deep(.n-card__content) {
    padding: 0 !important;
    background: transparent;
  }

  .mistake-new__panel {
    padding: 11px 12px;
    margin-bottom: 10px;
    border-radius: 14px;
    background: #fff;
    border: 1px solid rgba(226, 232, 240, 0.92);
    box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
  }

  .mistake-new__panel:last-child {
    margin-bottom: 0;
  }

  .mistake-new__section--main {
    padding-left: 0;
    border-left: none;
  }

  .mistake-new__grid :deep(.n-grid) {
    width: 100% !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
  }

  .mistake-new__grid :deep(.n-grid-item) {
    padding-left: 0 !important;
    padding-right: 0 !important;
  }

  .mistake-new__aside {
    gap: 0;
  }

  .mistake-new__section-title {
    display: flex;
    align-items: center;
    gap: 7px;
    margin-bottom: 8px;
    font-size: 12px;
    font-weight: 700;
    color: #4338ca;
    letter-spacing: 0.03em;
  }

  .mistake-new__section-title::before {
    content: "";
    width: 3px;
    height: 13px;
    border-radius: 999px;
    background: linear-gradient(180deg, #a5b4fc, #6366f1);
    flex-shrink: 0;
  }

  .mistake-new__meta-grid {
    gap: 8px 10px;
  }

  .mistake-new__item :deep(.n-form-item-label) {
    font-size: 12px;
    padding-bottom: 2px;
  }

  .mistake-new__stream-columns {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .mistake-new__stream-panel {
    margin-bottom: 10px;
    padding: 8px 10px;
    border-radius: 10px;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.07), rgba(129, 140, 248, 0.04));
  }

  .mistake-new__stream-tip--desktop {
    display: none;
  }

  .mistake-new__stream-tip--mobile {
    display: block;
    margin-bottom: 6px;
    font-size: 11px;
    line-height: 1.4;
  }

  .mistake-new__stream-pre {
    min-height: 52px;
    max-height: 108px;
    padding: 6px 8px;
    font-size: 11px;
    border-radius: 8px;
  }

  .mistake-new__section-head {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 8px;
  }

  .mistake-new__section-hint {
    font-size: 11px;
    width: auto;
  }

  .file-picker--compact {
    min-height: 84px;
    padding: 12px;
    border-radius: 12px;
  }

  .file-picker--compact .file-picker__hint {
    font-size: 12px;
  }

  .file-picker--compact .file-picker__sub {
    font-size: 11px;
  }

  .result-preview--compact {
    padding: 6px 8px;
    border-radius: 12px;
    background: rgba(248, 250, 252, 0.9);
  }

  .result-preview--compact img,
  .result-preview__image :deep(img) {
    max-height: min(26vh, 180px);
    border-radius: 10px;
  }

  .result-preview__zoom-hint {
    display: none;
  }

  .result-preview__actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 6px;
    justify-content: stretch;
    margin-top: 8px;
  }

  .result-preview__actions :deep(.n-tag) {
    grid-column: 1 / -1;
    justify-self: start;
    margin-bottom: 2px;
  }

  .result-preview__actions :deep(.n-button) {
    width: 100%;
    justify-content: center;
  }

  .mistake-new :deep(.formatted-analysis--panel) {
    overflow-x: auto;
    word-break: break-word;
    max-height: min(36vh, 280px);
    padding: 10px 11px;
  }

  .mistake-new :deep(.analysis-field__toolbar) {
    margin-bottom: 4px;
  }

  .mistake-new__regen-label--full {
    display: none;
  }

  .mistake-new__regen-label--short {
    display: inline;
  }

  .mistake-new__save-label--full {
    display: none;
  }

  .mistake-new__save-label--short {
    display: inline;
  }

  .mistake-new__footer--dock :deep(.n-button) {
    min-height: 40px;
    padding-left: 16px;
    padding-right: 16px;
  }

  .mistake-new__footer--dock :deep(.n-button--primary-type) {
    min-width: 96px;
  }
}

.file-picker--compact.file-picker--dragover {
  border-color: rgba(79, 70, 229, 0.65);
  background: rgba(99, 102, 241, 0.12);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}

.result-preview--compact.result-preview--dragover {
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.55);
  border-radius: 12px;
}

.file-picker--compact .file-picker__hint {
  font-size: 13px;
}

.file-picker--compact .file-picker__sub {
  font-size: 12px;
}

.result-preview--compact {
  padding: 8px 10px;
  border-radius: 12px;
}

.result-preview--compact img,
.result-preview__image :deep(img) {
  display: block;
  width: 100%;
  max-height: min(42vh, 320px);
  object-fit: contain;
  border-radius: 8px;
  margin: 0 auto;
  cursor: zoom-in;
}

.result-preview__zoom-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--app-text-subtle);
  text-align: center;
}

.result-preview__actions {
  margin-top: 6px;
}

.crop-modal :deep(.n-card-header) {
  padding: 10px 14px 6px;
}

.crop-modal :deep(.n-card-header__main) {
  font-size: 15px;
}

.crop-modal :deep(.n-card__content) {
  padding: 10px 14px 12px;
}

.crop-modal__intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.crop-modal__tip {
  font-size: 12px;
  line-height: 1.4;
  flex: 1;
  min-width: 140px;
}

.crop-zoom-bar {
  flex-shrink: 0;
}

.crop-zoom-bar__label {
  font-size: 12px;
  min-width: 36px;
  text-align: center;
}

.mistake-new__footer,
.crop-modal__footer,
.reanalyze-modal__footer {
  margin-top: 8px;
}

.reanalyze-modal__tip {
  display: block;
  font-size: 13px;
  line-height: 1.55;
  margin-bottom: 10px;
}

.reanalyze-modal__input {
  width: 100%;
}

.crop-modal-body {
  --crop-view-h: min(56vh, 480px);
  width: 100%;
  height: var(--crop-view-h);
  overflow: auto;
  border-radius: 8px;
  border: 1px solid var(--app-border);
  background: rgba(15, 23, 42, 0.04);
}

.crop-viewport {
  min-width: 100%;
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  box-sizing: border-box;
}

@media (max-width: 768px) {
  .crop-modal-body {
    --crop-view-h: min(50vh, 360px);
  }
}

.crop-stage {
  position: relative;
  display: inline-block;
  max-width: none;
  max-height: none;
  line-height: 0;
  cursor: crosshair;
  touch-action: none;
}

.crop-stage img {
  display: block;
  max-width: min(100%, 520px);
  max-height: calc(var(--crop-view-h) - 16px);
  width: auto;
  height: auto;
  object-fit: contain;
  user-select: none;
  pointer-events: none;
}

.crop-selection {
  position: absolute;
  box-sizing: border-box;
  border: none;
  box-shadow: inset 0 0 0 1px rgba(79, 70, 229, 0.95);
  background: rgba(99, 102, 241, 0.12);
  pointer-events: auto;
  border-radius: 2px;
}

.crop-selection__body {
  position: absolute;
  inset: 0;
  cursor: move;
}

.crop-handle {
  position: absolute;
  box-sizing: border-box;
  background: #fff;
  border: 1px solid rgba(79, 70, 229, 0.95);
  pointer-events: auto;
  z-index: 1;
}

.crop-handle--nw,
.crop-handle--ne,
.crop-handle--se,
.crop-handle--sw {
  width: 6px;
  height: 6px;
  border-radius: 1px;
}

.crop-handle--n,
.crop-handle--s {
  width: 8px;
  height: 4px;
  border-radius: 1px;
}

.crop-handle--e,
.crop-handle--w {
  width: 4px;
  height: 8px;
  border-radius: 1px;
}

.crop-handle--nw {
  top: 0;
  left: 0;
  transform: translate(-50%, -50%);
  cursor: nwse-resize;
}

.crop-handle--n {
  top: 0;
  left: 50%;
  transform: translate(-50%, -50%);
  cursor: ns-resize;
}

.crop-handle--ne {
  top: 0;
  right: 0;
  left: auto;
  transform: translate(50%, -50%);
  cursor: nesw-resize;
}

.crop-handle--e {
  top: 50%;
  right: 0;
  left: auto;
  transform: translate(50%, -50%);
  cursor: ew-resize;
}

.crop-handle--se {
  bottom: 0;
  right: 0;
  top: auto;
  left: auto;
  transform: translate(50%, 50%);
  cursor: nwse-resize;
}

.crop-handle--s {
  bottom: 0;
  left: 50%;
  top: auto;
  transform: translate(-50%, 50%);
  cursor: ns-resize;
}

.crop-handle--sw {
  bottom: 0;
  left: 0;
  top: auto;
  transform: translate(-50%, 50%);
  cursor: nesw-resize;
}

.crop-handle--w {
  top: 50%;
  left: 0;
  transform: translate(-50%, -50%);
  cursor: ew-resize;
}

.hidden-file-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

.result-preview {
  width: 100%;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid var(--app-border);
  background: rgba(255, 255, 255, 0.72);
  box-sizing: border-box;
}

.result-preview img {
  display: block;
  width: 100%;
  max-height: min(52vh, 520px);
  object-fit: contain;
  border-radius: 10px;
  margin: 0 auto;
}

.result-preview__image :deep(img) {
  cursor: zoom-in;
}
</style>
