<script setup lang="ts">
import Cropper from "cropperjs";
import "cropperjs/dist/cropper.css";
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import { NButton, NModal, NSlider, NSpace, useMessage } from "naive-ui";
import { AVATAR_CROP_OUTPUT_SIZE, canvasToAvatarFile, readFileAsObjectUrl } from "../utils/avatarImage";

const props = defineProps<{
  show: boolean;
  file: File | null;
}>();

const emit = defineEmits<{
  "update:show": [value: boolean];
  confirm: [file: File];
}>();

const message = useMessage();
const imgRef = ref<HTMLImageElement | null>(null);
const previewUrl = ref("");
const zoomSlider = ref(0);
const confirming = ref(false);

let cropper: Cropper | null = null;
let previewObjectUrl: string | null = null;

function revokePreview() {
  if (previewObjectUrl) {
    URL.revokeObjectURL(previewObjectUrl);
    previewObjectUrl = null;
  }
}

function destroyCropper() {
  if (cropper) {
    cropper.destroy();
    cropper = null;
  }
}

function syncZoomSlider() {
  if (!cropper) return;
  const imageData = cropper.getImageData();
  const ratio = imageData.width > 0 ? imageData.width / imageData.naturalWidth : 1;
  const min = 0.2;
  const max = 3;
  zoomSlider.value = Math.round(((ratio - min) / (max - min)) * 100);
  zoomSlider.value = Math.max(0, Math.min(100, zoomSlider.value));
}

function initCropper() {
  const img = imgRef.value;
  if (!img || !props.show) return;
  destroyCropper();
  cropper = new Cropper(img, {
    aspectRatio: 1,
    viewMode: 1,
    dragMode: "move",
    autoCropArea: 0.92,
    responsive: true,
    background: false,
    guides: true,
    center: true,
    highlight: false,
    cropBoxMovable: false,
    cropBoxResizable: false,
    toggleDragModeOnDblclick: false,
    ready() {
      syncZoomSlider();
    },
    zoom() {
      syncZoomSlider();
    },
  });
}

function applyZoomFromSlider(value: number) {
  if (!cropper) return;
  const min = 0.2;
  const max = 3;
  const ratio = min + (value / 100) * (max - min);
  cropper.zoomTo(ratio);
}

function zoomStep(delta: number) {
  if (!cropper) return;
  cropper.zoom(delta);
  syncZoomSlider();
}

function close() {
  emit("update:show", false);
}

async function confirm() {
  if (!cropper || !props.file) return;
  confirming.value = true;
  try {
    const canvas = cropper.getCroppedCanvas({
      width: AVATAR_CROP_OUTPUT_SIZE,
      height: AVATAR_CROP_OUTPUT_SIZE,
      imageSmoothingEnabled: true,
      imageSmoothingQuality: "high",
    });
    if (!canvas) {
      throw new Error("裁切失败");
    }
    const mime =
      props.file.type === "image/png"
        ? "image/png"
        : props.file.type === "image/webp"
          ? "image/webp"
          : "image/jpeg";
    const out = await canvasToAvatarFile(canvas, props.file.name, mime);
    emit("confirm", out);
    close();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    confirming.value = false;
  }
}

watch(
  () => [props.show, props.file] as const,
  async ([visible, file]) => {
    destroyCropper();
    revokePreview();
    previewUrl.value = "";
    zoomSlider.value = 0;
    if (!visible || !file) return;
    previewObjectUrl = readFileAsObjectUrl(file);
    previewUrl.value = previewObjectUrl;
    await nextTick();
    const img = imgRef.value;
    if (!img) return;
    if (img.complete) {
      initCropper();
    } else {
      img.onload = () => initCropper();
    }
  },
);

watch(
  () => props.show,
  (visible) => {
    if (!visible) {
      destroyCropper();
      revokePreview();
      previewUrl.value = "";
    }
  },
);

onBeforeUnmount(() => {
  destroyCropper();
  revokePreview();
});
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    title="裁切头像"
    class="avatar-crop-dialog"
    style="width: min(520px, 94vw)"
    :mask-closable="!confirming"
    @update:show="emit('update:show', $event)"
  >
    <p class="avatar-crop-dialog__hint">拖动图片调整位置，使用下方按钮或滑块缩放；裁切区域为正方形。</p>
    <div class="avatar-crop-dialog__stage">
      <img v-if="previewUrl" ref="imgRef" class="avatar-crop-dialog__img" :src="previewUrl" alt="" />
    </div>
    <div class="avatar-crop-dialog__zoom">
      <NButton size="small" secondary :disabled="confirming" @click="zoomStep(-0.12)">缩小</NButton>
      <NSlider
        v-model:value="zoomSlider"
        class="avatar-crop-dialog__slider"
        :min="0"
        :max="100"
        :step="1"
        :disabled="confirming"
        @update:value="applyZoomFromSlider"
      />
      <NButton size="small" secondary :disabled="confirming" @click="zoomStep(0.12)">放大</NButton>
    </div>
    <footer class="app-actions app-actions--bar avatar-crop-dialog__actions">
      <NSpace :size="8">
        <NButton :disabled="confirming" @click="close">取消</NButton>
        <NButton type="primary" :loading="confirming" @click="confirm">确认上传</NButton>
      </NSpace>
    </footer>
  </NModal>
</template>

<style scoped>
.avatar-crop-dialog__hint {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--app-text-muted, #64748b);
}

.avatar-crop-dialog__stage {
  width: 100%;
  height: min(360px, 52vh);
  min-height: 240px;
  border-radius: 12px;
  overflow: hidden;
  background: #0f172a;
}

.avatar-crop-dialog__img {
  display: block;
  max-width: 100%;
}

.avatar-crop-dialog__zoom {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
}

.avatar-crop-dialog__slider {
  flex: 1;
  min-width: 0;
}

.avatar-crop-dialog__actions {
  margin-top: 16px;
  padding-top: 12px;
}

@media (max-width: 768px) {
  .avatar-crop-dialog__stage {
    min-height: 200px;
    height: 44vh;
  }
}
</style>
