<script setup lang="ts">
import { computed, onActivated, onDeactivated, onMounted, ref, watch } from "vue";

defineOptions({ name: "MistakeSearchView" });
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NDatePicker,
  NIcon,
  NInput,
  NPopconfirm,
  NRadioButton,
  NRadioGroup,
  NSelect,
  NSpin,
  NTag,
  useMessage,
} from "naive-ui";
import type { SelectOption } from "naive-ui";
import FormattedAnalysis from "../components/FormattedAnalysis.vue";
import type { Grade, Mistake, MistakeListParams, Subject } from "../api/client";
import {
  deleteMistake,
  fetchGrades,
  fetchMistakeStatsTags,
  fetchMistakes,
  fetchSubjects,
} from "../api/client";
import { ERROR_REASON_OPTIONS, errorReasonLabel } from "../constants/errorReasons";
import {
  clearSearchScrollSnapshot,
  discardSearchScrollUnlessToDetail,
  saveSearchScrollSnapshot,
  scheduleSearchScrollRestore,
} from "../utils/searchScrollRestore";

const router = useRouter();
const route = useRoute();
const message = useMessage();

const GRADE_ALL = "__all__";
const SUBJECT_ALL = "__all__";

const loading = ref(false);
const searched = ref(false);
const filtersOpen = ref(false);
const results = ref<Mistake[]>([]);
const grades = ref<Grade[]>([]);
const subjects = ref<Subject[]>([]);
const tagOptions = ref<SelectOption[]>([]);

const searchText = ref("");
const selectedTags = ref<string[]>([]);
const tagMatch = ref<"and" | "or">("or");
const dateRange = ref<[number, number] | null>(null);
const hasImage = ref<"" | "yes" | "no">("");
const errorReasonCodes = ref<string[]>([]);
const gradeId = ref<string | null>(GRADE_ALL);
const subjectId = ref<string | null>(SUBJECT_ALL);
const mastery = ref<MistakeListParams["mastery"]>("all");

const gradeOptions = computed(() => [
  { label: "全部年级", value: GRADE_ALL },
  ...grades.value.map((g) => ({ label: g.name, value: g.id })),
]);

const subjectOptions = computed(() => [
  { label: "全部", value: SUBJECT_ALL },
  ...subjects.value.map((s) => ({ label: s.name, value: s.id })),
]);

const masteryOptions = [
  { label: "全部", value: "all" as const },
  { label: "未掌握", value: "unmastered" as const },
  { label: "已掌握", value: "mastered" as const },
];

const hasImageOptions = [
  { label: "配图不限", value: "" },
  { label: "含配图", value: "yes" },
  { label: "无配图", value: "no" },
];

const errorReasonOptions = ERROR_REASON_OPTIONS.map((o) => ({
  label: o.label,
  value: o.value,
}));

const resultCount = computed(() => results.value.length);

const activeFilterCount = computed(() => {
  let n = 0;
  if (selectedTags.value.length) n += 1;
  if (dateRange.value) n += 1;
  if (hasImage.value) n += 1;
  if (errorReasonCodes.value.length) n += 1;
  if (gradeId.value && gradeId.value !== GRADE_ALL) n += 1;
  if (subjectId.value && subjectId.value !== SUBJECT_ALL) n += 1;
  if (mastery.value !== "all") n += 1;
  return n;
});

const hasSideFilters = computed(() => activeFilterCount.value > 0 || searchText.value.trim().length > 0);

function formatDateParam(ts: number): string {
  const d = new Date(ts);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function buildParams(): MistakeListParams {
  const params: MistakeListParams = { mastery: mastery.value };
  const q = searchText.value.trim();
  if (q) params.q = q;
  if (selectedTags.value.length) {
    params.knowledge_tags = [...selectedTags.value];
    params.tag_match = tagMatch.value;
  }
  if (dateRange.value) {
    params.date_from = formatDateParam(dateRange.value[0]);
    params.date_to = formatDateParam(dateRange.value[1]);
  }
  if (hasImage.value === "yes") params.has_image = true;
  else if (hasImage.value === "no") params.has_image = false;
  if (errorReasonCodes.value.length) params.error_reasons = [...errorReasonCodes.value];
  if (gradeId.value && gradeId.value !== GRADE_ALL) params.grade_level_id = gradeId.value;
  if (subjectId.value && subjectId.value !== SUBJECT_ALL) params.subject_id = subjectId.value;
  return params;
}

function queryFromState(): Record<string, string> {
  const q: Record<string, string> = {};
  const text = searchText.value.trim();
  if (text) q.q = text;
  if (selectedTags.value.length) q.tags = selectedTags.value.join(",");
  if (tagMatch.value === "and") q.tag_match = "and";
  if (dateRange.value) {
    q.from = formatDateParam(dateRange.value[0]);
    q.to = formatDateParam(dateRange.value[1]);
  }
  if (hasImage.value) q.has_image = hasImage.value;
  if (errorReasonCodes.value.length) q.reasons = errorReasonCodes.value.join(",");
  if (gradeId.value && gradeId.value !== GRADE_ALL) q.grade = gradeId.value;
  if (subjectId.value && subjectId.value !== SUBJECT_ALL) q.subject = subjectId.value;
  if (mastery.value !== "all") q.mastery = mastery.value;
  if (filtersOpen.value) q.filters = "1";
  return q;
}

function syncRoute() {
  const next = queryFromState();
  const cur = route.query;
  const same =
    (next.q ?? "") === (typeof cur.q === "string" ? cur.q : "") &&
    (next.tags ?? "") === (typeof cur.tags === "string" ? cur.tags : "") &&
    (next.tag_match ?? "") === (typeof cur.tag_match === "string" ? cur.tag_match : "") &&
    (next.from ?? "") === (typeof cur.from === "string" ? cur.from : "") &&
    (next.to ?? "") === (typeof cur.to === "string" ? cur.to : "") &&
    (next.has_image ?? "") === (typeof cur.has_image === "string" ? cur.has_image : "") &&
    (next.reasons ?? "") === (typeof cur.reasons === "string" ? cur.reasons : "") &&
    (next.grade ?? "") === (typeof cur.grade === "string" ? cur.grade : "") &&
    (next.subject ?? "") === (typeof cur.subject === "string" ? cur.subject : "") &&
    (next.mastery ?? "") === (typeof cur.mastery === "string" ? cur.mastery : "") &&
    (next.filters ?? "") === (typeof cur.filters === "string" ? cur.filters : "");
  if (same) return;
  router.replace({ path: "/search", query: next });
}

function applyRouteQuery() {
  const rq = route.query;
  searchText.value = typeof rq.q === "string" ? rq.q : "";
  selectedTags.value =
    typeof rq.tags === "string" && rq.tags.trim()
      ? rq.tags.split(",").map((t) => t.trim()).filter(Boolean)
      : [];
  tagMatch.value = rq.tag_match === "and" ? "and" : "or";
  if (typeof rq.from === "string" && typeof rq.to === "string") {
    const a = Date.parse(rq.from);
    const b = Date.parse(rq.to);
    if (!Number.isNaN(a) && !Number.isNaN(b)) dateRange.value = [a, b];
    else dateRange.value = null;
  } else {
    dateRange.value = null;
  }
  hasImage.value =
    rq.has_image === "yes" || rq.has_image === "no" ? (rq.has_image as "yes" | "no") : "";
  errorReasonCodes.value =
    typeof rq.reasons === "string" && rq.reasons.trim()
      ? rq.reasons.split(",").filter(Boolean)
      : [];
  const g = typeof rq.grade === "string" ? rq.grade : null;
  gradeId.value = g && grades.value.some((x) => x.id === g) ? g : GRADE_ALL;
  mastery.value =
    rq.mastery === "mastered" || rq.mastery === "unmastered" ? rq.mastery : "all";
  filtersOpen.value = rq.filters === "1" || activeFilterCount.value > 0 || !!searchText.value.trim();
}

function applySubjectFromRoute() {
  const s = typeof route.query.subject === "string" ? route.query.subject : null;
  if (!s || s === "all") {
    subjectId.value = SUBJECT_ALL;
    return;
  }
  subjectId.value = subjects.value.some((x) => x.id === s) ? s : SUBJECT_ALL;
}

function routeQueryKey(): string {
  return JSON.stringify(route.query);
}

function hasSearchQueryInRoute(): boolean {
  return Object.keys(route.query).some((k) => k !== "filters");
}

async function hydrateFromRoute(andSearch: boolean) {
  applyRouteQuery();
  await loadSubjects();
  applySubjectFromRoute();
  await loadTagOptions();
  if (andSearch && hasSearchQueryInRoute()) {
    await runSearch({ syncRoute: false });
  }
}

async function loadSubjects() {
  const gid = gradeId.value && gradeId.value !== GRADE_ALL ? gradeId.value : undefined;
  subjects.value = await fetchSubjects(gid ? { grade_level_id: gid } : undefined);
  if (
    subjectId.value &&
    subjectId.value !== SUBJECT_ALL &&
    !subjects.value.some((s) => s.id === subjectId.value)
  ) {
    subjectId.value = SUBJECT_ALL;
  }
}

async function loadTagOptions() {
  const rows = await fetchMistakeStatsTags({
    grade_level_id: gradeId.value && gradeId.value !== GRADE_ALL ? gradeId.value : undefined,
    subject_id:
      subjectId.value && subjectId.value !== SUBJECT_ALL ? subjectId.value : undefined,
  });
  tagOptions.value = rows.map((r) => ({ label: `${r.tag}（${r.mistake_count}）`, value: r.tag }));
}

async function runSearch(opts?: { syncRoute?: boolean }) {
  loading.value = true;
  searched.value = true;
  if (opts?.syncRoute !== false) syncRoute();
  try {
    results.value = await fetchMistakes(buildParams());
  } catch (e) {
    message.error((e as Error).message);
    results.value = [];
  } finally {
    loading.value = false;
  }
}

function resetFilters() {
  searchText.value = "";
  selectedTags.value = [];
  tagMatch.value = "or";
  dateRange.value = null;
  hasImage.value = "";
  errorReasonCodes.value = [];
  gradeId.value = GRADE_ALL;
  subjectId.value = SUBJECT_ALL;
  mastery.value = "all";
  results.value = [];
  searched.value = false;
  filtersOpen.value = false;
  clearSearchScrollSnapshot();
  router.replace({ path: "/search" });
}

function formatDisplayDate(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}

async function onDelete(id: string) {
  try {
    await deleteMistake(id);
    message.success("已删除");
    await runSearch();
    void loadTagOptions();
  } catch (e) {
    message.error((e as Error).message);
  }
}

function openDetail(m: Mistake) {
  saveSearchScrollSnapshot(m.id);
  syncRoute();
  router.push({ path: `/mistakes/${m.id}`, query: { returnTo: route.fullPath } });
}

function toggleFilters() {
  filtersOpen.value = !filtersOpen.value;
}

watch(gradeId, async () => {
  await loadSubjects();
  void loadTagOptions();
});

watch(subjectId, () => {
  void loadTagOptions();
});

let lastRouteQueryKey = "";

onMounted(async () => {
  try {
    grades.value = await fetchGrades();
    lastRouteQueryKey = routeQueryKey();
    await hydrateFromRoute(true);
  } catch (e) {
    message.error((e as Error).message);
  }
});

onActivated(async () => {
  const key = routeQueryKey();
  if (key === lastRouteQueryKey) {
    scheduleSearchScrollRestore();
    return;
  }
  lastRouteQueryKey = key;
  try {
    if (!grades.value.length) grades.value = await fetchGrades();
    await hydrateFromRoute(true);
  } catch (e) {
    message.error((e as Error).message);
  }
});

onDeactivated(() => {
  lastRouteQueryKey = routeQueryKey();
  queueMicrotask(() => {
    discardSearchScrollUnlessToDetail(router.currentRoute.value.path);
  });
});
</script>

<template>
  <div class="mistake-search page-root">
    <section class="search-hero surface-card">
      <div class="search-hero__head">
        <div class="search-hero__title-wrap">
          <h1 class="search-hero__title">全局搜索</h1>
          <p class="search-hero__hint">题干 · 解析 · 知识点 · 组合筛选</p>
        </div>
        <div class="search-hero__head-actions">
          <NButton
            size="small"
            :type="filtersOpen ? 'primary' : 'default'"
            :secondary="!filtersOpen"
            @click="toggleFilters"
          >
            筛选
            <span v-if="activeFilterCount" class="search-hero__badge">{{ activeFilterCount }}</span>
          </NButton>
        </div>
      </div>

      <div class="search-hero__bar">
        <NInput
          v-model:value="searchText"
          size="medium"
          clearable
          placeholder="搜索题干、解析、答案或知识点…"
          class="search-hero__input"
          @keyup.enter="runSearch"
        >
          <template #prefix>
            <NIcon class="search-hero__icon" :depth="3">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <circle cx="11" cy="11" r="7" />
                <path d="m20 20-4.2-4.2" stroke-linecap="round" />
              </svg>
            </NIcon>
          </template>
        </NInput>
        <NButton type="primary" :loading="loading" class="search-hero__submit" @click="runSearch">
          搜索
        </NButton>
      </div>

      <div v-if="searched && !loading" class="search-hero__stat">
        共 <strong>{{ resultCount }}</strong> 条
        <span v-if="hasSideFilters" class="search-hero__stat-muted">· 已应用筛选</span>
      </div>
    </section>

    <section v-show="filtersOpen" class="search-filters surface-card">
      <div class="search-filters__grid">
        <NSelect v-model:value="gradeId" size="small" clearable :options="gradeOptions" placeholder="年级" />
        <NSelect v-model:value="subjectId" size="small" clearable :options="subjectOptions" placeholder="科目" />
        <NSelect v-model:value="mastery" size="small" clearable :options="masteryOptions" placeholder="掌握" />
        <NSelect v-model:value="hasImage" size="small" clearable :options="hasImageOptions" placeholder="配图" />
        <NDatePicker
          v-model:value="dateRange"
          size="small"
          type="daterange"
          clearable
          class="search-filters__date"
          start-placeholder="开始"
          end-placeholder="结束"
        />
        <NSelect
          v-model:value="errorReasonCodes"
          size="small"
          :options="errorReasonOptions"
          multiple
          clearable
          max-tag-count="responsive"
          placeholder="错因"
          class="search-filters__reasons"
        />
        <NSelect
          v-model:value="selectedTags"
          size="small"
          :options="tagOptions"
          multiple
          filterable
          tag
          clearable
          max-tag-count="responsive"
          placeholder="知识点标签"
          class="search-filters__tags"
        />
      </div>
      <div v-if="selectedTags.length > 1" class="search-filters__tag-mode">
        <NRadioGroup v-model:value="tagMatch" size="small">
          <NRadioButton value="or">OR</NRadioButton>
          <NRadioButton value="and">AND</NRadioButton>
        </NRadioGroup>
        <span class="search-filters__tag-hint">多标签匹配</span>
      </div>
      <div class="search-filters__actions app-actions">
        <NButton size="small" quaternary @click="resetFilters">清空</NButton>
        <NButton size="small" type="primary" :loading="loading" @click="runSearch">应用并搜索</NButton>
      </div>
    </section>

    <section v-if="searched" class="search-results">
      <NSpin :show="loading" class="search-results__spin">
        <ul v-if="results.length" class="search-results__list">
          <li
            v-for="m in results"
            :id="`search-result-${m.id}`"
            :key="m.id"
            class="search-tile surface-card"
            :class="{ 'search-tile--mastered': m.is_mastered }"
          >
            <span
              class="search-tile__accent"
              :class="m.is_mastered ? 'search-tile__accent--mastered' : 'search-tile__accent--pending'"
              aria-hidden="true"
            />
            <div
              class="search-tile__body"
              role="button"
              tabindex="0"
              @click="openDetail(m)"
              @keydown.enter="openDetail(m)"
            >
              <div class="search-tile__top">
                <span class="search-tile__date">{{ formatDisplayDate(m.created_at) }}</span>
                <div class="search-tile__badges">
                  <NTag v-if="m.grade_name" size="tiny" :bordered="false">{{ m.grade_name }}</NTag>
                  <NTag v-if="m.subject_name" size="tiny" :bordered="false" type="info">
                    {{ m.subject_name }}
                  </NTag>
                  <NTag
                    size="small"
                    :type="m.is_mastered ? 'success' : 'warning'"
                    :bordered="false"
                    class="search-tile__mastery"
                  >
                    {{ m.is_mastered ? "已掌握" : "未掌握" }}
                  </NTag>
                  <span v-if="m.error_reason" class="search-tile__reason">
                    {{ errorReasonLabel(m.error_reason) }}
                  </span>
                  <span v-if="m.image_path" class="search-tile__has-img">含配图</span>
                </div>
              </div>
              <div class="search-tile__stem search-tile__stem--formatted">
                <FormattedAnalysis :text="m.stem" variant="stem" empty-text="—" />
              </div>
              <div v-if="m.knowledge_tags?.length" class="search-tile__tags">
                <span v-for="t in m.knowledge_tags" :key="t" class="search-tile__tag">{{ t }}</span>
              </div>
            </div>
            <div class="search-tile__actions app-actions" @click.stop>
              <NButton
                size="small"
                secondary
                @click="router.push({ path: `/mistakes/${m.id}/edit`, query: { returnTo: route.fullPath } })"
              >
                编辑
              </NButton>
              <NPopconfirm positive-text="删除" negative-text="取消" @positive-click="onDelete(m.id)">
                <template #trigger>
                  <NButton size="small" type="error" secondary>删除</NButton>
                </template>
                确定删除这道错题？
              </NPopconfirm>
            </div>
          </li>
        </ul>
        <div v-else-if="!loading" class="search-results__empty">
          <p>未找到匹配错题</p>
          <NButton size="small" quaternary @click="resetFilters">清空条件</NButton>
        </div>
      </NSpin>
    </section>
  </div>
</template>

<style scoped>
.mistake-search {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 920px;
  margin: 0 auto;
  width: 100%;
}

.search-hero {
  padding: 12px 14px;
  border-radius: 14px;
  background:
    radial-gradient(ellipse 80% 100% at 100% 0%, rgba(99, 102, 241, 0.12), transparent 55%),
    linear-gradient(160deg, #fff 0%, #f8f9ff 100%);
  border: 1px solid rgba(255, 255, 255, 0.95);
  box-shadow:
    0 0 0 1px rgba(99, 102, 241, 0.06),
    var(--app-shadow);
}

.search-hero__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.search-hero__title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #0f172a;
  line-height: 1.2;
}

.search-hero__hint {
  margin: 2px 0 0;
  font-size: 11px;
  color: var(--app-text-muted, #64748b);
}

.search-hero__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  margin-left: 4px;
  padding: 0 4px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.25);
}

.search-hero__bar {
  display: flex;
  gap: 8px;
  align-items: stretch;
}

.search-hero__input {
  flex: 1;
  min-width: 0;
}

.search-hero__input :deep(.n-input) {
  border-radius: 10px;
}

.search-hero__icon {
  color: #94a3b8;
}

.search-hero__submit {
  flex-shrink: 0;
  border-radius: 10px;
  padding-left: 18px;
  padding-right: 18px;
}

.search-hero__stat {
  margin-top: 8px;
  font-size: 12px;
  color: var(--app-text-muted, #64748b);
}

.search-hero__stat strong {
  color: #4f46e5;
  font-weight: 700;
}

.search-hero__stat-muted {
  color: var(--app-text-subtle, #94a3b8);
}

.search-filters {
  padding: 10px 12px;
  border-radius: 12px;
  animation: search-filters-in 0.18s ease;
}

@keyframes search-filters-in {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.search-filters__grid {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.search-filters__date {
  grid-column: span 2;
}

.search-filters__reasons {
  grid-column: span 2;
}

.search-filters__tags {
  grid-column: 1 / -1;
}

.search-filters__tag-mode {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.search-filters__tag-hint {
  font-size: 11px;
  color: var(--app-text-subtle, #94a3b8);
}

.search-filters__actions {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(226, 232, 240, 0.7);
}

.search-results__spin :deep(.n-spin-container),
.search-results__spin :deep(.n-spin-content) {
  width: 100%;
}

.search-results__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.search-tile {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 0;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid rgba(226, 232, 240, 0.85);
  background: #fff;
  transition: box-shadow 0.15s ease, border-color 0.15s ease;
}

.search-tile:hover {
  box-shadow: var(--app-shadow);
  border-color: rgba(99, 102, 241, 0.22);
}

.search-tile--mastered {
  border-color: rgba(34, 197, 94, 0.32);
  background: linear-gradient(135deg, rgba(240, 253, 244, 0.95) 0%, rgba(255, 255, 255, 0.94) 48%);
}

.search-tile__accent {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
}

.search-tile__accent--pending {
  background: linear-gradient(180deg, #fbbf24, #f59e0b);
}

.search-tile__accent--mastered {
  background: linear-gradient(180deg, #34d399, #10b981);
}

.search-tile__body {
  padding: 12px 14px 10px 16px;
  cursor: pointer;
  min-width: 0;
}

.search-tile__top {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.search-tile__date {
  font-size: 12px;
  font-weight: 500;
  color: var(--app-text-muted, #64748b);
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(148, 163, 184, 0.12);
  flex-shrink: 0;
}

.search-tile__badges {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  flex: 1 1 auto;
  min-width: 0;
}

.search-tile__mastery {
  flex-shrink: 0;
}

.search-tile__reason {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
  white-space: nowrap;
}

.search-tile__has-img {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(79, 70, 229, 0.08);
  color: #4f46e5;
  white-space: nowrap;
}

.search-tile__stem {
  font-size: 14px;
  line-height: 1.55;
  color: #334155;
}

.search-tile__stem--formatted {
  max-height: calc(1.55em * 3 + 8px);
  overflow: hidden;
}

.search-tile__stem--formatted :deep(.formatted-analysis) {
  font-size: 14px;
  line-height: 1.55;
  color: #334155;
}

.search-tile__stem--formatted :deep(.formatted-analysis p) {
  margin: 0 0 4px;
}

.search-tile__stem--formatted :deep(.formatted-analysis p:last-child) {
  margin-bottom: 0;
}

.search-tile__stem--formatted :deep(.formatted-analysis .analysis-step) {
  margin-bottom: 6px;
  padding: 6px 8px;
}

.search-tile__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.search-tile__tag {
  font-size: 11px;
  font-weight: 500;
  line-height: 1.3;
  padding: 3px 8px;
  border-radius: 6px;
  color: #4f46e5;
  background: rgba(79, 70, 229, 0.08);
  border: 1px solid rgba(79, 70, 229, 0.12);
}

.search-tile__actions {
  box-sizing: border-box;
  width: 100%;
  padding: 10px 14px 12px;
  margin-top: 0;
  border-top: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(248, 250, 252, 0.65);
  border-bottom-left-radius: 13px;
  border-bottom-right-radius: 13px;
}

.search-tile__actions :deep(.n-button) {
  flex-shrink: 0;
}

.search-results__empty {
  text-align: center;
  padding: 28px 12px;
  font-size: 13px;
  color: var(--app-text-muted, #64748b);
}

.search-results__empty p {
  margin: 0 0 8px;
}

@media (max-width: 768px) {
  .mistake-search {
    gap: 8px;
  }

  .search-hero {
    padding: 10px 12px;
  }

  .search-hero__head {
    margin-bottom: 8px;
  }

  .search-hero__bar {
    flex-direction: column;
  }

  .search-hero__submit {
    width: 100%;
  }

  .search-filters__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .search-filters__date,
  .search-filters__reasons {
    grid-column: span 2;
  }

  .search-tile__top {
    flex-direction: column;
    align-items: flex-start;
  }

  .search-tile__badges {
    justify-content: flex-start;
  }
}
</style>
