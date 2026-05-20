<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { fetchUserAvatarObjectUrl } from "../api/client";
import { useAuthStore } from "../stores/auth";
import { defaultAvatarPublicUrl } from "../utils/userAvatar";

const props = withDefaults(
  defineProps<{
    userId: string;
    gender?: string | null;
    hasCustomAvatar?: boolean;
    /** 本地预览地址（未保存前），优先于接口拉取 */
    previewSrc?: string | null;
    size?: number;
    fallbackText?: string;
    refreshKey?: string | number;
  }>(),
  { size: 32, fallbackText: "?", hasCustomAvatar: false, refreshKey: "", previewSrc: null },
);

const auth = useAuthStore();
const src = ref("");
const loadFailed = ref(false);
let blobUrl: string | null = null;

const staticSrc = computed(() => defaultAvatarPublicUrl(props.gender));
const sizeStyle = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  fontSize: `${Math.max(12, Math.round(props.size * 0.38))}px`,
}));

function onImgError() {
  if (blobUrl) {
    revokeBlob();
    loadFailed.value = true;
    src.value = staticSrc.value;
    return;
  }
  loadFailed.value = true;
  src.value = "";
}

function revokeBlob() {
  if (blobUrl) {
    URL.revokeObjectURL(blobUrl);
    blobUrl = null;
  }
}

async function load() {
  loadFailed.value = false;

  if (props.previewSrc) {
    revokeBlob();
    src.value = props.previewSrc;
    return;
  }

  if (!props.userId) {
    revokeBlob();
    src.value = "";
    return;
  }

  if (!props.hasCustomAvatar) {
    revokeBlob();
    src.value = staticSrc.value;
    return;
  }

  if (!auth.token) return;

  try {
    const url = await fetchUserAvatarObjectUrl(props.userId);
    revokeBlob();
    blobUrl = url;
    src.value = blobUrl;
  } catch {
    revokeBlob();
    loadFailed.value = true;
    src.value = staticSrc.value;
  }
}

watch(
  () =>
    [
      props.userId,
      props.previewSrc ?? "",
      props.gender,
      props.hasCustomAvatar,
      props.refreshKey,
      auth.token,
    ] as const,
  load,
  { immediate: true },
);

onBeforeUnmount(revokeBlob);

defineExpose({ reload: load });
</script>

<template>
  <span class="user-avatar" :style="sizeStyle" role="img" :aria-label="fallbackText">
    <img v-if="src" :key="src" class="user-avatar__img" :src="src" alt="" @error="onImgError" />
    <span v-else class="user-avatar__fallback">{{ fallbackText }}</span>
  </span>
</template>

<style scoped>
.user-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  background: linear-gradient(145deg, #6366f1, #8b5cf6);
  color: #fff;
  font-weight: 700;
  line-height: 1;
}

.user-avatar__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.user-avatar__fallback {
  user-select: none;
}
</style>
