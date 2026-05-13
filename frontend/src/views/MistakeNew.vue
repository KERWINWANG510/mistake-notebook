<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NFormItem,
  NGrid,
  NGridItem,
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
import { analyzeImage, createMistake, fetchGrades, fetchSubjects, solveFromStem } from "../api/client";

const router = useRouter();
const message = useMessage();

const subjects = ref<Subject[]>([]);
const grades = ref<Grade[]>([]);
const loadingMeta = ref(true);
const analyzing = ref(false);
const solvingStem = ref(false);
const saving = ref(false);
const hasRecognized = ref(false);

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

const fileInputRef = ref<HTMLInputElement | null>(null);

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

function onPickFile(e: Event) {
  const input = e.target as HTMLInputElement;
  const f = input.files?.[0] ?? null;
  input.value = "";
  if (!f) return;
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
  hasRecognized.value = false;
  originalFile.value = f;
  fileName.value = f.name;
  previewUrl.value = URL.createObjectURL(f);
  resetZoom();
  showCropModal.value = true;
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
  showCropModal.value = false;
  await runAnalyze();
}

function cancelCrop() {
  showCropModal.value = false;
  resetImageState();
}

function reopenCropModal() {
  if (!originalFile.value || !previewUrl.value) return;
  selRect.value = null;
  resetZoom();
  showCropModal.value = true;
}

onMounted(async () => {
  try {
    const [ss, gs] = await Promise.all([fetchSubjects(), fetchGrades()]);
    subjects.value = ss;
    grades.value = gs;
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loadingMeta.value = false;
  }
});

onBeforeUnmount(() => {
  detachCropListeners();
  revokePreview();
  revokeResultPreview();
});

const subjectOptions = computed(() => subjects.value.map((s) => ({ label: s.name, value: s.id })));
const gradeOptions = computed(() => grades.value.map((g) => ({ label: g.name, value: g.id })));

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
const analyzeSpinDesc = computed(() =>
  solvingStem.value ? "正在根据题干生成解析…" : "AI 识别中…",
);

function applySolveSuggestions(
  res: {
    analysis: string;
    answer: string;
    suggested_subject_code: string | null;
    suggested_grade_level: number | null;
  },
  opts?: { fallbackSubject?: boolean },
) {
  analysis.value = res.analysis;
  answer.value = res.answer;
  const subj = subjects.value.find((s) => s.code === res.suggested_subject_code);
  if (subj) {
    subjectId.value = subj.id;
  } else if (opts?.fallbackSubject) {
    subjectId.value = subjects.value[0]?.id ?? null;
  }
  if (res.suggested_grade_level != null) {
    const g = grades.value.find((x) => x.level === res.suggested_grade_level);
    if (g) gradeLevelId.value = g.id;
  }
}

async function runAnalyze() {
  if (!uploadFile.value) {
    message.warning("请先选择题目图片并完成框选确认");
    return;
  }
  analyzing.value = true;
  try {
    const res = await analyzeImage(uploadFile.value);
    stem.value = res.stem;
    applySolveSuggestions(res, { fallbackSubject: true });
    hasRecognized.value = true;
    message.success(usedCropRegion.value ? "已按框选区域识别，请核对题干并保存" : "识别完成，请核对题干并保存");
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    analyzing.value = false;
  }
}

async function runSolveFromStem() {
  const text = stem.value.trim();
  if (!text) {
    message.warning("请先填写题干");
    return;
  }
  solvingStem.value = true;
  try {
    const res = await solveFromStem(text);
    applySolveSuggestions(res);
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
    <div class="mistake-new page-root">
      <header class="page-header mistake-new__header">
        <h1 class="page-header__title">录入错题</h1>
        <p class="page-header__desc">上传并框选题目后自动识别；可修改题干后重新生成解析与答案。</p>
      </header>
      <NCard class="surface-card mistake-new__card" size="small" :bordered="false">
        <NSpin :show="analyzeBusy" :description="analyzeSpinDesc">
          <input
            id="mistake-image-input"
            ref="fileInputRef"
            type="file"
            accept="image/*"
            class="hidden-file-input"
            @change="onPickFile"
          />

          <NGrid class="mistake-new__grid" :cols="24" :x-gap="20" :y-gap="16" item-responsive responsive="screen">
            <NGridItem class="mistake-new__aside" span="24 l:9">
              <section class="mistake-new__section">
                <h2 class="mistake-new__section-title">题目图片</h2>
                <label v-if="!resultPreviewUrl" class="file-picker file-picker--compact" for="mistake-image-input">
                  <div class="file-picker__text">
                    <div class="file-picker__hint">选择或拍摄题目图片</div>
                    <div class="file-picker__sub">上传后弹窗框选识别区域</div>
                  </div>
                </label>
                <div v-else class="result-preview result-preview--compact">
                  <img :src="resultPreviewUrl" alt="已确认的题目区域" />
                  <NSpace align="center" wrap :size="6" class="result-preview__actions">
                    <NTag v-if="usedCropRegion" size="small" type="info" :bordered="false">已框选</NTag>
                    <NTag v-else size="small" :bordered="false">整张图</NTag>
                    <NButton size="tiny" tertiary @click="reopenCropModal">重新框选</NButton>
                    <NButton size="tiny" secondary :loading="analyzing" :disabled="analyzeBusy || !uploadFile" @click="runAnalyze">
                      重新识别
                    </NButton>
                    <NButton size="tiny" quaternary @click="pickAnotherImage">更换图片</NButton>
                  </NSpace>
                </div>
              </section>

              <section class="mistake-new__section">
                <h2 class="mistake-new__section-title">分类信息</h2>
                <NSpace vertical :size="10" style="width: 100%">
                  <NFormItem label="科目" :show-feedback="false" class="mistake-new__item" label-placement="top">
                    <NSelect
                      v-model:value="subjectId"
                      size="small"
                      :options="subjectOptions"
                      placeholder="请选择科目"
                    />
                  </NFormItem>
                  <NFormItem label="年级" :show-feedback="false" class="mistake-new__item" label-placement="top">
                    <NSelect
                      v-model:value="gradeLevelId"
                      size="small"
                      :options="gradeOptions"
                      placeholder="请选择年级"
                    />
                  </NFormItem>
                </NSpace>
              </section>
            </NGridItem>

            <NGridItem span="24 l:15">
              <section class="mistake-new__section mistake-new__section--main">
                <div class="mistake-new__section-head">
                  <h2 class="mistake-new__section-title">题干与解答</h2>
                  <NText v-if="hasRecognized" depth="3" class="mistake-new__section-hint">修改题干后可重新生成</NText>
                </div>

                <NSpace vertical :size="12" style="width: 100%">
                  <NFormItem label="题干" :show-feedback="false" class="mistake-new__item" label-placement="top">
                    <NSpace vertical :size="8" style="width: 100%">
                      <NInput
                        v-model:value="stem"
                        type="textarea"
                        size="small"
                        placeholder="识别结果可在此修改"
                        :autosize="{ minRows: 4, maxRows: 14 }"
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
                        根据题干重新生成解析与答案
                      </NButton>
                    </NSpace>
                  </NFormItem>

                  <NFormItem label="解题思路" :show-feedback="false" class="mistake-new__item" label-placement="top">
                    <NInput
                      v-model:value="analysis"
                      type="textarea"
                      size="small"
                      placeholder="解题步骤与思路"
                      :autosize="{ minRows: 4, maxRows: 14 }"
                    />
                  </NFormItem>

                  <NFormItem label="答案" :show-feedback="false" class="mistake-new__item" label-placement="top">
                    <NInput
                      v-model:value="answer"
                      type="textarea"
                      size="small"
                      placeholder="最终答案"
                      :autosize="{ minRows: 2, maxRows: 10 }"
                    />
                  </NFormItem>
                </NSpace>
              </section>
            </NGridItem>
          </NGrid>

          <footer class="mistake-new__footer">
            <NButton class="mistake-new__footer-btn" size="small" @click="router.push('/mistakes')">返回</NButton>
            <NButton
              class="mistake-new__footer-btn"
              type="primary"
              size="small"
              :loading="saving"
              :disabled="analyzeBusy || !uploadFile"
              @click="save"
            >
              保存到错题本
            </NButton>
          </footer>
        </NSpin>
      </NCard>
    </div>

    <NModal
      v-model:show="showCropModal"
      preset="card"
      title="框选题目区域"
      class="crop-modal"
      style="width: min(560px, 94vw)"
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
      <NSpace justify="space-between" align="center" wrap class="crop-modal__footer">
        <NButton size="tiny" secondary :disabled="!selRect" @click="clearSelection">清除选区</NButton>
        <NSpace :size="6" wrap>
          <NButton size="small" @click="cancelCrop">取消</NButton>
          <NButton size="small" :disabled="!imgLoaded" @click="confirmCrop(true)">整张图</NButton>
          <NButton type="primary" size="small" :disabled="!imgLoaded" @click="confirmCrop(false)">确定选区</NButton>
        </NSpace>
      </NSpace>
    </NModal>
  </NSpin>
</template>

<style scoped>
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
}

.mistake-new__grid {
  width: 100%;
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

.mistake-new__item {
  margin-bottom: 0;
}

.mistake-new__item :deep(.n-form-item-label) {
  padding-bottom: 4px;
  font-size: 13px;
  font-weight: 500;
}

.mistake-new__footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--app-border);
}

@media (max-width: 768px) {
  .mistake-new__card :deep(.n-card__content) {
    padding: 12px 14px;
  }

  .mistake-new__footer {
    flex-direction: column-reverse;
    align-items: stretch;
  }

  .mistake-new__footer-btn {
    width: 100%;
  }

  .mistake-new__section--main {
    padding-left: 0;
    border-left: none;
  }
}

.file-picker--compact {
  min-height: 72px;
  padding: 12px 14px;
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

.result-preview--compact img {
  max-height: min(42vh, 320px);
  border-radius: 8px;
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

.crop-modal__footer {
  margin-top: 8px;
}

.crop-modal-body {
  --crop-view-h: min(50vh, 400px);
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
    --crop-view-h: min(44vh, 320px);
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
</style>
