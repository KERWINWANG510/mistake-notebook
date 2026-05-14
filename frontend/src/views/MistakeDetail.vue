<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NImage, NSpace, NSpin, NTag, useMessage } from "naive-ui";
import FormattedAnalysis from "../components/FormattedAnalysis.vue";
import type { Mistake } from "../api/client";
import { fetchMistake, fetchMistakeImageObjectUrl, updateMistake } from "../api/client";

const route = useRoute();
const router = useRouter();
const message = useMessage();

const id = computed(() => route.params.id as string);
const loading = ref(true);
const row = ref<Mistake | null>(null);
const imageObjectUrl = ref<string | null>(null);
const marking = ref(false);

async function loadImageBlob() {
  if (imageObjectUrl.value) {
    URL.revokeObjectURL(imageObjectUrl.value);
    imageObjectUrl.value = null;
  }
  if (!row.value?.image_path) return;
  try {
    imageObjectUrl.value = await fetchMistakeImageObjectUrl(id.value);
  } catch {
    imageObjectUrl.value = null;
  }
}

async function load() {
  loading.value = true;
  try {
    row.value = await fetchMistake(id.value);
    await loadImageBlob();
  } catch (e) {
    message.error((e as Error).message);
    router.push("/mistakes");
  } finally {
    loading.value = false;
  }
}

onMounted(load);

onBeforeUnmount(() => {
  if (imageObjectUrl.value) URL.revokeObjectURL(imageObjectUrl.value);
});

function backToList() {
  const grade = row.value?.grade_level_id ?? (typeof route.query.grade === "string" ? route.query.grade : null);
  const subject = row.value?.subject_id ?? (typeof route.query.subject === "string" ? route.query.subject : null);
  if (grade && subject) {
    router.push({ path: "/mistakes", query: { grade, subject } });
    return;
  }
  router.push("/mistakes");
}

async function markMastered() {
  marking.value = true;
  try {
    row.value = await updateMistake(id.value, { is_mastered: true });
    message.success("已标记为已掌握");
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    marking.value = false;
  }
}
</script>

<template>
  <NSpin :show="loading">
    <div v-if="row" class="mistake-detail page-root page-root--fixed-actions">
      <header class="page-header mistake-detail__header">
        <h1 class="page-header__title">错题详情</h1>
        <p class="page-header__desc">仅供查看与复习；需要修改请返回列表点击「编辑」。</p>
      </header>

      <NCard class="surface-card mistake-detail__card" size="small" :bordered="false">
        <NSpace vertical :size="16" style="width: 100%">
          <section v-if="imageObjectUrl" class="mistake-detail__section">
            <h2 class="mistake-detail__section-title">题目图片</h2>
            <NImage
              width="100%"
              class="mistake-detail__image"
              :src="imageObjectUrl"
              object-fit="contain"
            />
          </section>
          <p v-else-if="row.image_path" class="mistake-detail__muted">图片暂时无法显示，请检查网络后刷新。</p>

          <section class="mistake-detail__section">
            <h2 class="mistake-detail__section-title">分类</h2>
            <NSpace wrap :size="8">
              <NTag size="small" type="info">{{ row.subject_name ?? "—" }}</NTag>
              <NTag size="small">{{ row.grade_name ?? "—" }}</NTag>
              <NTag v-if="row.is_mastered" size="small" type="success">已掌握</NTag>
              <NTag v-else size="small">未掌握</NTag>
              <NTag v-for="t in row.knowledge_tags ?? []" :key="t" size="small" type="info">{{ t }}</NTag>
            </NSpace>
          </section>

          <section class="mistake-detail__section">
            <h2 class="mistake-detail__section-title">题干</h2>
            <div class="mistake-detail__text mistake-detail__text--analysis">
              <FormattedAnalysis :text="row.stem" variant="stem" empty-text="—" />
            </div>
          </section>

          <section class="mistake-detail__section">
            <h2 class="mistake-detail__section-title">解题思路</h2>
            <div class="mistake-detail__text mistake-detail__text--analysis">
              <FormattedAnalysis :text="row.analysis" />
            </div>
          </section>

          <section class="mistake-detail__section">
            <h2 class="mistake-detail__section-title">答案</h2>
            <div class="mistake-detail__text">{{ row.answer || "—" }}</div>
          </section>
        </NSpace>
      </NCard>

      <Teleport to="body">
        <footer class="app-actions app-actions--bar app-actions--fixed">
          <div class="app-actions--fixed-inner">
            <NButton
              v-if="!row.is_mastered"
              size="small"
              type="success"
              secondary
              :loading="marking"
              @click="markMastered"
            >
              标记为已掌握
            </NButton>
            <NButton size="small" type="primary" @click="router.push({ path: `/mistakes/${id}/practice`, query: route.query })">
              举一反三
            </NButton>
            <NButton size="small" @click="backToList">返回列表</NButton>
            <NButton size="small" type="primary" secondary @click="router.push(`/mistakes/${id}/edit`)">编辑</NButton>
          </div>
        </footer>
      </Teleport>
    </div>
  </NSpin>
</template>

<style scoped>
.mistake-detail__header {
  margin-bottom: 12px;
}

.mistake-detail__card :deep(.n-card__content) {
  padding: 16px 18px;
}

.mistake-detail__section-title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.mistake-detail__image {
  max-width: 520px;
  border-radius: 12px;
}

.mistake-detail__text {
  margin: 0;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--app-border);
  background: rgba(255, 255, 255, 0.72);
  font-size: 14px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
  color: #0f172a;
}

.mistake-detail__muted {
  margin: 0;
  font-size: 14px;
  color: var(--app-text-muted);
}

.mistake-detail__text--analysis {
  padding: 12px 14px;
}
</style>
