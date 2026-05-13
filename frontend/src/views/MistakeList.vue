<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NEllipsis, NPopconfirm, NSelect, NSpin, NTag, useMessage } from "naive-ui";
import type { Grade, Mistake, SubjectMistakeSummary } from "../api/client";
import { deleteMistake, fetchGrades, fetchMistakes, fetchSubjectMistakeSummary } from "../api/client";
import { useAuthStore } from "../stores/auth";
import {
  inferCurrentGradeLevel,
  resolveGradeByLevel,
  subjectAccent,
  subjectInitial,
} from "../utils/inferGrade";

const router = useRouter();
const route = useRoute();
const message = useMessage();
const auth = useAuthStore();

type ViewMode = "subjects" | "mistakes";
type MasteryFilter = "unmastered" | "mastered" | "all";

const loading = ref(true);
const mistakesLoading = ref(false);
const grades = ref<Grade[]>([]);
const selectedGradeId = ref<string | null>(null);
const inferredGradeId = ref<string | null>(null);
const subjectSummaries = ref<SubjectMistakeSummary[]>([]);
const mistakes = ref<Mistake[]>([]);
const viewMode = ref<ViewMode>("subjects");
const activeSubject = ref<SubjectMistakeSummary | null>(null);
const masteryFilter = ref<MasteryFilter>("unmastered");
const masteryOptions = [
  { label: "未掌握", value: "unmastered" as const },
  { label: "已掌握", value: "mastered" as const },
  { label: "全部", value: "all" as const },
];
let initializing = true;

function hubQueryFromState(): Record<string, string> {
  const query: Record<string, string> = {};
  if (selectedGradeId.value) query.grade = selectedGradeId.value;
  if (viewMode.value === "mistakes" && activeSubject.value) {
    query.subject = activeSubject.value.subject_id;
  }
  return query;
}

function routeQueryMatchesState(): boolean {
  const next = hubQueryFromState();
  const grade = typeof route.query.grade === "string" ? route.query.grade : undefined;
  const subject = typeof route.query.subject === "string" ? route.query.subject : undefined;
  return next.grade === grade && next.subject === subject;
}

function syncRouteQuery() {
  if (route.path !== "/mistakes") return;
  const next = hubQueryFromState();
  if (routeQueryMatchesState()) return;
  router.replace({ path: "/mistakes", query: next });
}

function applyRouteQuery() {
  const qSubject = typeof route.query.subject === "string" ? route.query.subject : null;
  if (!qSubject) {
    viewMode.value = "subjects";
    activeSubject.value = null;
    mistakes.value = [];
    return;
  }

  const qGrade = typeof route.query.grade === "string" ? route.query.grade : null;
  if (qGrade && grades.value.some((g) => g.id === qGrade)) {
    selectedGradeId.value = qGrade;
  }

  const summary = subjectSummaries.value.find((s) => s.subject_id === qSubject);
  if (summary) {
    activeSubject.value = summary;
    viewMode.value = "mistakes";
    void loadMistakes();
    return;
  }

  viewMode.value = "subjects";
  activeSubject.value = null;
  mistakes.value = [];
}

const gradeOptions = computed(() => grades.value.map((g) => ({ label: g.name, value: g.id })));

const selectedGrade = computed(() => grades.value.find((g) => g.id === selectedGradeId.value) ?? null);

const totalMistakeCount = computed(() => subjectSummaries.value.reduce((sum, s) => sum + s.mistake_count, 0));

const gradeHint = computed(() => {
  const user = auth.me;
  if (!user?.education_stage || user.enrollment_year == null) {
    return "选择年级查看科目";
  }
  if (selectedGradeId.value === inferredGradeId.value && inferredGradeId.value) {
    return "已按档案自动推断年级";
  }
  return "已手动切换年级";
});

const headerSubtitle = computed(() => {
  if (viewMode.value === "mistakes" && activeSubject.value) {
    return `${selectedGrade.value?.name ?? ""} · ${activeSubject.value.mistake_count} 道错题`;
  }
  if (totalMistakeCount.value > 0) {
    return `${selectedGrade.value?.name ?? "当前年级"} · 共 ${totalMistakeCount.value} 道错题`;
  }
  return gradeHint.value;
});

function applyInferredGrade() {
  const level = inferCurrentGradeLevel(auth.me);
  const grade = resolveGradeByLevel(level, grades.value);
  inferredGradeId.value = grade?.id ?? null;
  if (!selectedGradeId.value && grade) {
    selectedGradeId.value = grade.id;
  }
}

async function loadGrades() {
  grades.value = await fetchGrades();
  applyInferredGrade();
  if (!selectedGradeId.value && grades.value.length > 0) {
    selectedGradeId.value = grades.value[0].id;
  }
}

async function loadSubjectSummaries() {
  if (!selectedGradeId.value) {
    subjectSummaries.value = [];
    return;
  }
  loading.value = true;
  try {
    subjectSummaries.value = await fetchSubjectMistakeSummary(selectedGradeId.value);
  } catch (e) {
    message.error((e as Error).message);
    subjectSummaries.value = [];
  } finally {
    loading.value = false;
  }
}

async function loadMistakes() {
  if (!selectedGradeId.value || !activeSubject.value) {
    mistakes.value = [];
    return;
  }
  mistakesLoading.value = true;
  try {
    mistakes.value = await fetchMistakes({
      grade_level_id: selectedGradeId.value,
      subject_id: activeSubject.value.subject_id,
      mastery: masteryFilter.value,
    });
  } catch (e) {
    message.error((e as Error).message);
    mistakes.value = [];
  } finally {
    mistakesLoading.value = false;
  }
}

async function init() {
  loading.value = true;
  try {
    if (!auth.me) await auth.fetchMe();
    await loadGrades();

    const qGrade = typeof route.query.grade === "string" ? route.query.grade : null;
    if (qGrade && grades.value.some((g) => g.id === qGrade)) {
      selectedGradeId.value = qGrade;
    }

    await loadSubjectSummaries();
    applyRouteQuery();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
    initializing = false;
  }
}

onMounted(init);

watch(
  () => ({ grade: route.query.grade, subject: route.query.subject }),
  () => {
    if (initializing || route.path !== "/mistakes") return;
    applyRouteQuery();
  },
);

watch(selectedGradeId, async () => {
  if (initializing) return;
  if (viewMode.value === "mistakes") {
    viewMode.value = "subjects";
    activeSubject.value = null;
    mistakes.value = [];
  }
  syncRouteQuery();
  await loadSubjectSummaries();
});

watch(masteryFilter, () => {
  if (initializing || viewMode.value !== "mistakes" || !activeSubject.value) return;
  void loadMistakes();
});

function openSubject(summary: SubjectMistakeSummary) {
  activeSubject.value = summary;
  viewMode.value = "mistakes";
  syncRouteQuery();
  void loadMistakes();
}

function backToSubjects() {
  viewMode.value = "subjects";
  activeSubject.value = null;
  mistakes.value = [];
  syncRouteQuery();
}

function resetToInferred() {
  if (inferredGradeId.value) {
    selectedGradeId.value = inferredGradeId.value;
  }
}

async function onDelete(id: string) {
  try {
    await deleteMistake(id);
    message.success("已删除");
    await loadMistakes();
    await loadSubjectSummaries();
    if (mistakes.value.length === 0) {
      backToSubjects();
    }
  } catch (e) {
    message.error((e as Error).message);
  }
}

function formatDate(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}
</script>

<template>
  <div class="mistake-hub page-root">
    <section
      class="mistake-hub__header"
      :class="{
        'mistake-hub__header--subjects': viewMode === 'subjects',
        'mistake-hub__header--mistakes': viewMode === 'mistakes',
        'mistake-hub__header--grade-overridden':
          inferredGradeId != null && selectedGradeId !== inferredGradeId,
      }"
    >
      <div class="mistake-hub__header-top">
        <div class="mistake-hub__header-left">
          <NButton
            v-if="viewMode === 'mistakes'"
            class="mistake-hub__back"
            quaternary
            size="small"
            @click="backToSubjects"
          >
            ←
          </NButton>
          <div class="mistake-hub__title-wrap">
            <h1 class="mistake-hub__title">
              {{ viewMode === "mistakes" && activeSubject ? activeSubject.subject_name : "错题本" }}
            </h1>
            <p class="mistake-hub__subtitle">{{ headerSubtitle }}</p>
          </div>
        </div>
        <div class="mistake-hub__header-actions">
          <NSelect
            v-if="viewMode === 'mistakes'"
            v-model:value="masteryFilter"
            class="mistake-hub__mastery-select"
            size="small"
            :options="masteryOptions"
            placeholder="是否掌握"
          />
          <NSelect
            v-model:value="selectedGradeId"
            class="mistake-hub__grade-select"
            size="small"
            :options="gradeOptions"
            placeholder="年级"
          />
          <NButton
            v-if="inferredGradeId && selectedGradeId !== inferredGradeId"
            class="mistake-hub__reset-inferred"
            quaternary
            size="tiny"
            @click="resetToInferred"
          >
            <span class="mistake-hub__reset-label mistake-hub__reset-label--full">恢复推断</span>
            <span class="mistake-hub__reset-label mistake-hub__reset-label--short">推断</span>
          </NButton>
          <NButton class="mistake-hub__add-btn" type="primary" size="small" @click="router.push('/mistakes/new')">
            <span class="mistake-hub__add-label mistake-hub__add-label--full">录入错题</span>
            <span class="mistake-hub__add-label mistake-hub__add-label--short">录入</span>
          </NButton>
        </div>
      </div>
    </section>

    <NSpin :show="loading && viewMode === 'subjects'">
      <section v-if="viewMode === 'subjects'" class="mistake-hub__panel">
        <div v-if="subjectSummaries.length > 0" class="mistake-hub__subject-grid">
          <button
            v-for="item in subjectSummaries"
            :key="item.subject_id"
            type="button"
            class="subject-tile"
            :style="{
              background: subjectAccent(item.subject_code).bg,
              '--tile-fg': subjectAccent(item.subject_code).fg,
              '--tile-ring': subjectAccent(item.subject_code).ring,
            }"
            @click="openSubject(item)"
          >
            <div class="subject-tile__badge">{{ item.mistake_count }}</div>
            <div class="subject-tile__avatar">{{ subjectInitial(item.subject_name) }}</div>
            <div class="subject-tile__name">{{ item.subject_name }}</div>
            <p class="subject-tile__meta">{{ item.mistake_count }} 道错题</p>
            <span class="subject-tile__arrow" aria-hidden="true">→</span>
          </button>
        </div>

        <div v-else-if="!loading" class="mistake-hub__empty">
          <div class="mistake-hub__empty-icon">📚</div>
          <p class="mistake-hub__empty-title">该年级暂无错题</p>
          <p class="mistake-hub__empty-desc">切换其他年级查看，或录入第一道错题</p>
          <NButton type="primary" @click="router.push('/mistakes/new')">去录入</NButton>
        </div>
      </section>
    </NSpin>

    <section v-if="viewMode === 'mistakes' && activeSubject" class="mistake-hub__panel mistake-hub__panel--grow">
      <NSpin :show="mistakesLoading" class="mistake-hub__spin">
        <div v-if="mistakes.length > 0" class="mistake-hub__mistake-grid">
          <article
            v-for="m in mistakes"
            :key="m.id"
            class="mistake-tile"
            :class="{ 'mistake-tile--mastered': m.is_mastered }"
            role="button"
            tabindex="0"
            @click="router.push({ path: `/mistakes/${m.id}`, query: route.query })"
            @keydown.enter="router.push({ path: `/mistakes/${m.id}`, query: route.query })"
          >
            <div class="mistake-tile__top">
              <span class="mistake-tile__date">{{ formatDate(m.created_at) }}</span>
              <div class="mistake-tile__badges">
                <NTag
                  size="small"
                  :type="m.is_mastered ? 'success' : 'warning'"
                  :bordered="false"
                  class="mistake-tile__mastery"
                >
                  {{ m.is_mastered ? "已掌握" : "未掌握" }}
                </NTag>
                <span v-if="m.image_path" class="mistake-tile__has-img">含配图</span>
              </div>
            </div>
            <NEllipsis :line-clamp="4" class="mistake-tile__stem">{{ m.stem }}</NEllipsis>
            <div class="mistake-tile__actions app-actions app-actions--bar" @click.stop>
              <NButton size="small" secondary @click="router.push(`/mistakes/${m.id}/edit`)">编辑</NButton>
              <NPopconfirm positive-text="删除" negative-text="取消" @positive-click="onDelete(m.id)">
                <template #trigger>
                  <NButton size="small" type="error" secondary>删除</NButton>
                </template>
                确定删除这道错题？
              </NPopconfirm>
            </div>
          </article>
        </div>
        <div v-else-if="!mistakesLoading" class="mistake-hub__empty">
          <p class="mistake-hub__empty-title">当前筛选条件下暂无错题</p>
        </div>
      </NSpin>
    </section>
  </div>
</template>

<style scoped>
.mistake-hub {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.mistake-hub__panel--grow {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.mistake-hub__panel--grow :deep(.n-spin-container) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.mistake-hub__panel--grow :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
}

.mistake-hub__header {
  border-radius: 16px;
  padding: 12px 14px;
  background:
    radial-gradient(ellipse 80% 120% at 100% 0%, rgba(99, 102, 241, 0.14), transparent 55%),
    linear-gradient(145deg, #ffffff 0%, #f8f9ff 100%);
  border: 1px solid rgba(255, 255, 255, 0.9);
  box-shadow: var(--app-shadow);
}

.mistake-hub__header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.mistake-hub__header-left {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1 1 160px;
  min-width: 0;
}

.mistake-hub__title-wrap {
  min-width: 0;
}

.mistake-hub__title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #0f172a;
  line-height: 1.25;
}

.mistake-hub__subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--app-text-muted);
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mistake-hub__header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.mistake-hub__grade-select {
  width: 108px;
}

.mistake-hub__mastery-select {
  width: 108px;
}

.mistake-hub__back {
  flex-shrink: 0;
  padding: 0 8px !important;
}

.mistake-hub__panel {
  padding: 0;
}

.mistake-hub__subject-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 160px), 1fr));
  gap: 12px;
}

.subject-tile {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  min-height: 148px;
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.85);
  border-radius: 18px;
  text-align: left;
  cursor: pointer;
  box-shadow: 0 6px 24px rgba(15, 23, 42, 0.05);
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease;
  -webkit-tap-highlight-color: transparent;
}

.subject-tile:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
}

.subject-tile:active {
  transform: scale(0.985);
}

.subject-tile__badge {
  position: absolute;
  top: 12px;
  right: 12px;
  min-width: 28px;
  height: 28px;
  padding: 0 8px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: var(--tile-fg);
  background: #fff;
  border: 1px solid var(--tile-ring);
}

.subject-tile__avatar {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 800;
  color: var(--tile-fg);
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid var(--tile-ring);
  margin-bottom: 4px;
}

.subject-tile__name {
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
}

.subject-tile__meta {
  margin: 0;
  font-size: 12px;
  color: var(--app-text-muted);
}

.subject-tile__arrow {
  position: absolute;
  right: 16px;
  bottom: 14px;
  font-size: 16px;
  color: var(--tile-fg);
  opacity: 0.55;
}

.mistake-hub__mistake-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 280px), 1fr));
  gap: 12px;
  align-content: start;
}

.mistake-tile {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border-radius: 16px;
  background: #fff;
  border: 1px solid var(--app-border);
  box-shadow: var(--app-shadow);
  min-height: 140px;
  cursor: pointer;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease;
  -webkit-tap-highlight-color: transparent;
}

.mistake-tile:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 28px rgba(15, 23, 42, 0.07);
  border-color: rgba(99, 102, 241, 0.28);
}

.mistake-tile:focus-visible {
  outline: 2px solid rgba(99, 102, 241, 0.45);
  outline-offset: 2px;
}

.mistake-tile__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.mistake-tile__badges {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.mistake-tile--mastered {
  border-color: rgba(34, 197, 94, 0.28);
  background: linear-gradient(180deg, rgba(240, 253, 244, 0.92), rgba(255, 255, 255, 0.88));
}

.mistake-tile__date {
  font-size: 12px;
  color: var(--app-text-subtle);
}

.mistake-tile__has-img {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(79, 70, 229, 0.08);
  color: #4f46e5;
}

.mistake-tile__stem {
  flex: 1;
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
}

.mistake-hub__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 48px 20px;
  text-align: center;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.65);
  border: 1px dashed rgba(148, 163, 184, 0.45);
}

.mistake-hub__empty-icon {
  font-size: 2rem;
}

.mistake-hub__empty-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #334155;
}

.mistake-hub__empty-desc {
  margin: 0 0 4px;
  font-size: 13px;
  color: var(--app-text-muted);
  max-width: 280px;
}

.mistake-hub__add-label--short {
  display: none;
}

.mistake-hub__reset-label--short {
  display: none;
}

@media (max-width: 768px) {
  .mistake-hub {
    gap: 8px;
  }

  .mistake-hub__header {
    padding: 8px 10px;
    border-radius: 12px;
    background: #fff;
    box-shadow: 0 1px 6px rgba(15, 23, 42, 0.05);
  }

  .mistake-hub__header-top {
    flex-direction: row;
    align-items: center;
    flex-wrap: nowrap;
    gap: 8px;
  }

  .mistake-hub__header-left {
    flex: 0 0 auto;
    min-width: 0;
  }

  .mistake-hub__title {
    font-size: 1.05rem;
  }

  .mistake-hub__header-actions {
    flex: 1 1 auto;
    min-width: 0;
    justify-content: flex-end;
  }

  .mistake-hub__grade-select {
    flex: 1 1 auto;
    width: auto;
    min-width: 0;
    max-width: 108px;
  }

  .mistake-hub__mastery-select {
    flex: 1 1 auto;
    width: auto;
    min-width: 0;
    max-width: 108px;
  }

  .mistake-hub__add-btn {
    flex-shrink: 0;
    padding-left: 10px !important;
    padding-right: 10px !important;
  }

  .mistake-hub__add-label--full {
    display: none;
  }

  .mistake-hub__add-label--short {
    display: inline;
  }

  .mistake-hub__header--subjects .mistake-hub__subtitle {
    display: none;
  }

  .mistake-hub__reset-inferred {
    flex-shrink: 0;
    padding-left: 6px !important;
    padding-right: 6px !important;
    font-size: 12px;
  }

  .mistake-hub__reset-label--full {
    display: none;
  }

  .mistake-hub__reset-label--short {
    display: inline;
  }

  .mistake-hub__header--grade-overridden .mistake-hub__grade-select {
    max-width: 92px;
  }

  .mistake-hub__header--mistakes .mistake-hub__subtitle {
    font-size: 11px;
    margin-top: 0;
  }

  .mistake-hub__header--mistakes .mistake-hub__title-wrap {
    flex: 1;
    min-width: 0;
  }
}
</style>
