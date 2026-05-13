<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { NButton, NCard, NEllipsis, NSpace, NSelect, NSpin, NTag, useMessage } from "naive-ui";
import type { Mistake, Subject, Grade } from "../api/client";
import { deleteMistake, fetchGrades, fetchMistakes, fetchSubjects } from "../api/client";

const router = useRouter();
const message = useMessage();

const loading = ref(true);
const rows = ref<Mistake[]>([]);
const subjects = ref<Subject[]>([]);
const grades = ref<Grade[]>([]);
const subjectFilter = ref<string | null>(null);
const gradeFilter = ref<string | null>(null);

async function load() {
  loading.value = true;
  try {
    const [ms, ss, gs] = await Promise.all([fetchMistakes(), fetchSubjects(), fetchGrades()]);
    rows.value = ms;
    subjects.value = ss;
    grades.value = gs;
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}

onMounted(load);

async function onDelete(id: string) {
  try {
    await deleteMistake(id);
    message.success("已删除");
    await load();
  } catch (e) {
    message.error((e as Error).message);
  }
}

async function applyFilter() {
  loading.value = true;
  try {
    rows.value = await fetchMistakes({
      subject_id: subjectFilter.value ?? undefined,
      grade_level_id: gradeFilter.value ?? undefined,
    });
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <NSpace vertical :size="16" class="page-root">
    <header class="page-header mistake-list__header">
      <div class="mistake-list__header-main">
        <h1 class="page-header__title">错题本</h1>
        <p class="page-header__desc">按科目、年级筛选；可查看、编辑或删除错题。</p>
      </div>
      <NButton class="mistake-list__add-btn" type="primary" @click="router.push('/mistakes/new')">录入错题</NButton>
    </header>
    <NCard class="surface-card" title="我的错题" :segmented="{ content: true }">
      <NSpace vertical :size="12" style="width: 100%">
        <div class="mistake-list__filters">
          <NSelect
            v-model:value="subjectFilter"
            clearable
            class="mistake-list__filter-select"
            placeholder="按科目筛选"
            :options="subjects.map((s) => ({ label: s.name, value: s.id }))"
          />
          <NSelect
            v-model:value="gradeFilter"
            clearable
            class="mistake-list__filter-select"
            placeholder="按年级筛选"
            :options="grades.map((g) => ({ label: g.name, value: g.id }))"
          />
          <NButton type="primary" @click="applyFilter">筛选</NButton>
          <NButton @click="(subjectFilter = null), (gradeFilter = null), load()">重置</NButton>
        </div>

        <NSpin :show="loading">
          <div class="entity-card-list mistake-card-grid">
            <NCard v-for="m in rows" :key="m.id" class="entity-card mistake-row-card" size="small" embedded>
              <div class="entity-card__tags">
                <NTag size="small" type="info">{{ m.subject_name ?? "—" }}</NTag>
                <NTag size="small">{{ m.grade_name ?? "—" }}</NTag>
              </div>
              <NEllipsis :line-clamp="3" class="entity-card__preview">{{ m.stem }}</NEllipsis>
              <div class="entity-card__actions">
                <NButton size="small" @click="router.push(`/mistakes/${m.id}`)">查看</NButton>
                <NButton size="small" secondary @click="router.push(`/mistakes/${m.id}/edit`)">编辑</NButton>
                <NButton size="small" type="error" secondary @click="onDelete(m.id)">删除</NButton>
              </div>
            </NCard>
            <div v-if="!loading && rows.length === 0" class="entity-card__empty">暂无错题，点击上方「录入错题」开始添加</div>
          </div>
        </NSpin>
      </NSpace>
    </NCard>
  </NSpace>
</template>

<style scoped>
.mistake-card-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

@media (min-width: 769px) {
  .mistake-card-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.mistake-card-grid .entity-card__empty {
  grid-column: 1 / -1;
}

.mistake-row-card {
  height: 100%;
}

.mistake-row-card :deep(.n-card__content) {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.mistake-row-card .entity-card__preview {
  flex: 1;
  min-height: 0;
}

.mistake-list__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.mistake-list__header-main {
  flex: 1;
  min-width: 0;
}

.mistake-list__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  width: 100%;
}

.mistake-list__filter-select {
  flex: 1 1 148px;
  min-width: 0;
  max-width: 100%;
}

@media (max-width: 768px) {
  .mistake-list__add-btn {
    width: 100%;
  }

  .mistake-list__filter-select {
    flex: 1 1 100%;
  }

  .entity-card__actions {
    justify-content: stretch;
  }

  .entity-card__actions :deep(.n-button) {
    flex: 1 1 calc(33.33% - 6px);
    min-width: 72px;
  }
}
</style>
