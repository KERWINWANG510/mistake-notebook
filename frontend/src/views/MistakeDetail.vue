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

const knowledgeTagList = computed(() => row.value?.knowledge_tags?.filter((t) => t?.trim()) ?? []);

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
        <p class="page-header__desc">用于查看与复习；需要修改请点击底部「编辑」，也可在错题列表中编辑。</p>
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

          <section class="mistake-detail__section mistake-detail__section--meta">
            <h2 class="mistake-detail__section-title">分类信息</h2>
            <div class="mistake-detail__meta-board">
              <div class="mistake-detail__meta-top">
                <div class="mistake-detail__meta-kv">
                  <span class="mistake-detail__meta-k">科目</span>
                  <span class="mistake-detail__meta-v">{{ row.subject_name ?? "—" }}</span>
                </div>
                <span class="mistake-detail__meta-dot" aria-hidden="true" />
                <div class="mistake-detail__meta-kv">
                  <span class="mistake-detail__meta-k">年级</span>
                  <span class="mistake-detail__meta-v">{{ row.grade_name ?? "—" }}</span>
                </div>
                <span class="mistake-detail__meta-dot" aria-hidden="true" />
                <div class="mistake-detail__meta-kv">
                  <span class="mistake-detail__meta-k">错因</span>
                  <span class="mistake-detail__meta-v">{{ row.error_reason_label || "—" }}</span>
                </div>
                <span class="mistake-detail__meta-dot" aria-hidden="true" />
                <div class="mistake-detail__meta-kv mistake-detail__meta-kv--tag">
                  <span class="mistake-detail__meta-k">掌握</span>
                  <NTag
                    v-if="row.is_mastered"
                    size="tiny"
                    type="success"
                    round
                    :bordered="false"
                    class="mistake-detail__mastery-tag"
                  >
                    已掌握
                  </NTag>
                  <NTag v-else size="tiny" type="warning" round :bordered="false" class="mistake-detail__mastery-tag">
                    未掌握
                  </NTag>
                </div>
              </div>
              <div class="mistake-detail__meta-tags-row">
                <span class="mistake-detail__meta-k">知识点</span>
                <div v-if="knowledgeTagList.length" class="mistake-detail__meta-tags">
                  <NTag
                    v-for="t in knowledgeTagList"
                    :key="t"
                    size="tiny"
                    class="mistake-detail__knowledge-tag"
                    round
                    :bordered="false"
                  >
                    {{ t }}
                  </NTag>
                </div>
                <span v-else class="mistake-detail__meta-empty">暂无</span>
              </div>
            </div>
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
            <NButton
              size="small"
              type="primary"
              secondary
              @click="router.push({ path: `/mistakes/${id}/edit`, query: { returnTo: route.fullPath } })"
            >
              编辑
            </NButton>
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

.mistake-detail__section--meta .mistake-detail__section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 12px;
  color: #64748b;
}

.mistake-detail__section--meta .mistake-detail__section-title::before {
  content: "";
  width: 2px;
  height: 12px;
  border-radius: 999px;
  background: linear-gradient(180deg, #a5b4fc, #6366f1);
  flex-shrink: 0;
}

.mistake-detail__meta-board {
  border-radius: 10px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.04);
  overflow: hidden;
}

.mistake-detail__meta-top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 0;
  padding: 8px 10px;
  border-bottom: 1px solid rgba(241, 245, 249, 0.95);
  font-size: 13px;
  line-height: 1.35;
}

.mistake-detail__meta-kv {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  max-width: 100%;
  min-width: 0;
}

.mistake-detail__meta-kv--tag {
  align-items: center;
}

.mistake-detail__meta-k {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
}

.mistake-detail__meta-v {
  font-weight: 600;
  color: #0f172a;
  word-break: break-word;
}

.mistake-detail__meta-dot {
  width: 4px;
  height: 4px;
  margin: 0 8px;
  border-radius: 50%;
  background: #cbd5e1;
  flex-shrink: 0;
}

.mistake-detail__mastery-tag {
  font-weight: 600;
}

.mistake-detail__meta-tags-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 6px 8px;
  padding: 8px 10px;
}

.mistake-detail__meta-tags-row > .mistake-detail__meta-k {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  min-height: 22px;
  line-height: 1;
}

.mistake-detail__meta-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  flex: 1;
  min-width: 0;
  min-height: 22px;
}

.mistake-detail__meta-tags :deep(.n-tag) {
  margin: 0;
}

.mistake-detail__knowledge-tag {
  font-weight: 500;
  font-size: 12px;
  background: rgba(99, 102, 241, 0.09) !important;
  color: #4338ca !important;
}

.mistake-detail__meta-empty {
  display: inline-flex;
  align-items: center;
  flex: 1;
  min-width: 0;
  min-height: 22px;
  font-size: 12px;
  line-height: 1;
  color: #94a3b8;
}

@media (max-width: 768px) {
  .mistake-detail__meta-top {
    padding: 7px 8px;
    font-size: 12px;
  }

  .mistake-detail__meta-dot {
    margin: 0 6px;
  }

  .mistake-detail__meta-tags-row {
    padding: 5px 8px 7px;
  }
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
