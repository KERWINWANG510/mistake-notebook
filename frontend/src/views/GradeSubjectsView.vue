<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import type { DropdownOption } from "naive-ui";
import { NCard, NCollapse, NCollapseItem, NDropdown, NSpin, useMessage } from "naive-ui";
import type { GradeWithSubjects, SubjectMistakeSummary } from "../api/client";
import { fetchGradeCatalog, fetchSubjectMistakeSummary } from "../api/client";

const router = useRouter();
const message = useMessage();
const loading = ref(true);
const catalog = ref<GradeWithSubjects[]>([]);
const expandedNames = ref<string[]>([]);
const summariesByGrade = ref<Record<string, SubjectMistakeSummary[]>>({});
const summariesLoading = ref<Record<string, boolean>>({});

const totalSubjectSlots = computed(() =>
  catalog.value.reduce((sum, g) => sum + g.subjects.length, 0),
);

async function load() {
  loading.value = true;
  try {
    catalog.value = await fetchGradeCatalog();
    if (catalog.value.length > 0 && expandedNames.value.length === 0) {
      expandedNames.value = [catalog.value[0].id];
    }
  } catch (e) {
    message.error((e as Error).message);
    catalog.value = [];
  } finally {
    loading.value = false;
  }
}

async function ensureGradeSummaries(gradeId: string) {
  if (summariesByGrade.value[gradeId] || summariesLoading.value[gradeId]) return;
  summariesLoading.value[gradeId] = true;
  try {
    summariesByGrade.value[gradeId] = await fetchSubjectMistakeSummary(gradeId);
  } catch (e) {
    message.error((e as Error).message);
    summariesByGrade.value[gradeId] = [];
  } finally {
    summariesLoading.value[gradeId] = false;
  }
}

function summaryFor(gradeId: string, subjectId: string): SubjectMistakeSummary | undefined {
  return summariesByGrade.value[gradeId]?.find((s) => s.subject_id === subjectId);
}

function subjectTagMenuOptions(gradeId: string, subjectId: string): DropdownOption[] {
  const summary = summaryFor(gradeId, subjectId);
  return (summary?.knowledge_tags ?? []).map((t) => ({
    label: `${t.tag}（${t.count}）`,
    key: t.tag,
  }));
}

function goMistakes(gradeId: string, subjectId: string, tag?: string) {
  const query: Record<string, string> = { grade: gradeId, subject: subjectId };
  if (tag) query.tag = tag;
  router.push({ path: "/mistakes", query });
}

function onSubjectTagSelect(tag: string | number, gradeId: string, subjectId: string) {
  goMistakes(gradeId, subjectId, String(tag));
}

watch(
  expandedNames,
  (names) => {
    for (const id of names) void ensureGradeSummaries(id);
  },
  { immediate: true },
);

onMounted(load);
</script>

<template>
  <div class="page-root grade-subjects">
    <header class="page-header">
      <h1 class="page-header__title">年级科目</h1>
      <p class="page-header__desc">
        按年级查看系统内置的重要科目（语数英、政史地、理化生等）。点击科目进入错题列表；若该科已有错题并打了知识点标签，可点右侧小三角按标签筛选。
      </p>
    </header>

    <NCard class="surface-card" :segmented="{ content: true }">
      <template #header>
        <div class="grade-subjects__card-head">
          <span>年级与科目</span>
          <span v-if="!loading" class="grade-subjects__meta">
            {{ catalog.length }} 个年级 · {{ totalSubjectSlots }} 项开设关系
          </span>
        </div>
      </template>

      <NSpin :show="loading">
        <NCollapse v-if="catalog.length > 0" v-model:expanded-names="expandedNames" class="grade-subjects__collapse">
          <NCollapseItem
            v-for="grade in catalog"
            :key="grade.id"
            :name="grade.id"
            :title="grade.name"
          >
            <template #header-extra>
              <span class="grade-subjects__count">{{ grade.subjects.length }} 科</span>
            </template>
            <NSpin :show="!!summariesLoading[grade.id]" size="small">
              <div class="grade-subjects__subject-list">
                <div
                  v-for="subject in grade.subjects"
                  :key="subject.id"
                  class="grade-subjects__subject-chip"
                >
                  <button
                    type="button"
                    class="grade-subjects__subject-main"
                    @click="goMistakes(grade.id, subject.id)"
                  >
                    {{ subject.name }}
                    <span v-if="summaryFor(grade.id, subject.id)?.mistake_count" class="grade-subjects__subject-count">
                      {{ summaryFor(grade.id, subject.id)?.mistake_count }}
                    </span>
                  </button>
                  <NDropdown
                    v-if="subjectTagMenuOptions(grade.id, subject.id).length"
                    trigger="click"
                    :options="subjectTagMenuOptions(grade.id, subject.id)"
                    @select="(key) => onSubjectTagSelect(key, grade.id, subject.id)"
                  >
                    <button
                      type="button"
                      class="grade-subjects__subject-menu"
                      aria-label="按知识点查看错题"
                      @click.stop
                    >
                      ▾
                    </button>
                  </NDropdown>
                </div>
              </div>
            </NSpin>
          </NCollapseItem>
        </NCollapse>
        <div v-else-if="!loading" class="grade-subjects__empty">暂无年级科目数据</div>
      </NSpin>
    </NCard>
  </div>
</template>

<style scoped>
.grade-subjects__card-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
}

.grade-subjects__meta {
  font-size: 12px;
  font-weight: 400;
  color: var(--app-text-muted);
}

.grade-subjects__count {
  font-size: 12px;
  color: var(--app-text-muted);
}

.grade-subjects__collapse :deep(.n-collapse-item__header) {
  font-weight: 600;
}

.grade-subjects__subject-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.grade-subjects__subject-chip {
  display: inline-flex;
  align-items: stretch;
  max-width: 100%;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid rgba(99, 102, 241, 0.22);
  background: rgba(99, 102, 241, 0.06);
}

.grade-subjects__subject-main {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: none;
  background: transparent;
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  cursor: pointer;
}

.grade-subjects__subject-main:hover {
  background: rgba(255, 255, 255, 0.55);
}

.grade-subjects__subject-count {
  min-width: 18px;
  padding: 0 6px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  line-height: 18px;
  text-align: center;
  color: #4f46e5;
  background: rgba(255, 255, 255, 0.9);
}

.grade-subjects__subject-menu {
  width: 30px;
  border: none;
  border-left: 1px solid rgba(99, 102, 241, 0.18);
  background: rgba(255, 255, 255, 0.45);
  color: #4f46e5;
  font-size: 13px;
  cursor: pointer;
}

.grade-subjects__subject-menu:hover {
  background: rgba(255, 255, 255, 0.85);
}

.grade-subjects__empty {
  padding: 32px 16px;
  text-align: center;
  color: var(--app-text-muted);
  font-size: 14px;
}

@media (max-width: 768px) {
  .grade-subjects__card-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
