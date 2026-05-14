<script setup lang="ts">
import type { EChartsOption } from "echarts";
import * as echarts from "echarts";
import { NCard, NSelect, NSpin, NStatistic, useMessage } from "naive-ui";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { Grade, MistakeStatsOverview, MistakeStatsTagRow, Subject } from "../api/client";
import {
  fetchGrades,
  fetchMistakeStatsOverview,
  fetchMistakeStatsTags,
  fetchSubjects,
} from "../api/client";

const message = useMessage();
const loading = ref(true);
const tagLoading = ref(false);
const overview = ref<MistakeStatsOverview | null>(null);

const grades = ref<Grade[]>([]);
const tagSubjects = ref<Subject[]>([]);
const tagGradeId = ref<string | null>(null);
const tagSubjectId = ref<string | null>(null);

const wrapGrade = ref<HTMLDivElement | null>(null);
const wrapSubject = ref<HTMLDivElement | null>(null);
const wrapTag = ref<HTMLDivElement | null>(null);

const narrow = ref(false);
function updateNarrow() {
  narrow.value = window.matchMedia("(max-width: 768px)").matches;
}

let chartGrade: ReturnType<typeof echarts.init> | null = null;
let chartSubject: ReturnType<typeof echarts.init> | null = null;
let chartTag: ReturnType<typeof echarts.init> | null = null;

const CHART_GRADE_MIN = 340;
const CHART_EMPTY_H = 300;
const CHART_ROW_H = 44;

/** 各柱使用不同渐变色（循环） */
const BAR_PALETTE: [string, string][] = [
  ["#818cf8", "#6366f1"],
  ["#34d399", "#10b981"],
  ["#fbbf24", "#f59e0b"],
  ["#f472b6", "#ec4899"],
  ["#38bdf8", "#0ea5e9"],
  ["#a78bfa", "#8b5cf6"],
  ["#fb923c", "#ea580c"],
  ["#4ade80", "#16a34a"],
  ["#f87171", "#dc2626"],
  ["#2dd4bf", "#0d9488"],
];

const gradeFilterOptions = computed(() =>
  grades.value.map((g) => ({ label: g.name, value: g.id })),
);

const subjectFilterOptions = computed(() =>
  tagSubjects.value.map((s) => ({ label: s.name, value: s.id })),
);

function chartHeightGrade(count: number) {
  return Math.min(440, Math.max(CHART_GRADE_MIN, 280 + count * 30));
}

function chartHeightHorizontal(names: string[], compact = false) {
  const n = Math.max(names.length, 1);
  const maxLen = names.length ? Math.max(...names.map((s) => s.length)) : 0;
  const rowH = compact ? 38 : CHART_ROW_H;
  const extra = maxLen > 14 ? Math.min(compact ? 100 : 140, (maxLen - 14) * (compact ? 5 : 7)) : 0;
  const minH = compact ? 280 : 340;
  const cap = compact ? 620 : 760;
  return Math.min(cap, Math.max(minH, 96 + n * rowH + extra));
}

function barGradient(index: number, horizontal: boolean) {
  const [c0, c1] = BAR_PALETTE[index % BAR_PALETTE.length];
  return new echarts.graphic.LinearGradient(0, 0, horizontal ? 1 : 0, horizontal ? 0 : 1, [
    { offset: 0, color: c0 },
    { offset: 1, color: c1 },
  ]);
}

function coloredBarData(values: number[], horizontal: boolean) {
  const radius: [number, number, number, number] = horizontal ? [0, 6, 6, 0] : [6, 6, 0, 0];
  return values.map((value, index) => ({
    value,
    itemStyle: {
      color: barGradient(index, horizontal),
      borderRadius: radius,
    },
  }));
}

function emptyOption(sub: string): EChartsOption {
  return {
    title: {
      text: "暂无数据",
      subtext: sub,
      left: "center",
      top: "center",
      textStyle: { fontSize: 15, color: "#94a3b8", fontWeight: 500 },
      subtextStyle: { fontSize: 12, color: "#cbd5e1" },
    },
  };
}

function verticalBar(names: string[], values: number[], yName: string, compact = false): EChartsOption {
  const rotate = names.length > 8 ? 36 : names.length > 4 ? 26 : 0;
  const bottom = rotate ? "26%" : names.length > 6 ? "20%" : compact ? "14%" : "16%";
  const fontSize = compact ? 11 : 12;
  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (p: unknown) => {
        const arr = Array.isArray(p) ? p : [p];
        const first = arr[0] as { name?: string; value?: number };
        return `${first?.name ?? ""}<br/>${yName}：${first?.value ?? 0}`;
      },
    },
    grid: {
      left: "4%",
      right: rotate ? "22%" : "18%",
      bottom,
      top: compact ? "10%" : "12%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: names,
      axisLabel: {
        rotate,
        interval: 0,
        color: "#64748b",
        fontSize,
        lineHeight: compact ? 16 : 18,
        hideOverlap: false,
      },
    },
    yAxis: {
      type: "value",
      name: yName,
      nameTextStyle: { color: "#64748b", fontSize },
      axisLabel: { color: "#64748b", fontSize },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    series: [
      {
        type: "bar",
        data: coloredBarData(values, false),
        barMaxWidth: compact ? 36 : 44,
      },
    ],
  };
}

function horizontalGridRightPx(values: number[]) {
  const maxVal = values.length ? Math.max(0, ...values) : 0;
  const digitLen = Math.max(1, String(Math.ceil(maxVal)).length);
  return Math.min(168, Math.max(96, 64 + digitLen * 14));
}

function horizontalBar(names: string[], values: number[], xName: string, compact = false): EChartsOption {
  const gridRight = horizontalGridRightPx(values);
  const fontSize = compact ? 11 : 12;
  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (p: unknown) => {
        const arr = Array.isArray(p) ? p : [p];
        const first = arr[0] as { name?: string; value?: number };
        return `${first?.name ?? ""}<br/>${xName}：${first?.value ?? 0}`;
      },
    },
    grid: {
      left: compact ? 6 : 12,
      right: compact ? Math.max(72, gridRight - 16) : gridRight,
      bottom: compact ? 32 : 44,
      top: compact ? 32 : 44,
      containLabel: true,
    },
    xAxis: {
      type: "value",
      name: xName,
      nameLocation: "middle",
      nameGap: compact ? 22 : 28,
      nameTextStyle: { color: "#64748b", fontSize },
      axisLabel: {
        color: "#64748b",
        fontSize,
        margin: compact ? 6 : 10,
        hideOverlap: false,
      },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    yAxis: {
      type: "category",
      data: names,
      axisLabel: {
        color: "#475569",
        fontSize,
        lineHeight: compact ? 18 : 20,
        margin: compact ? 10 : 14,
        width: compact ? 168 : 280,
        overflow: "break",
      },
      inverse: true,
    },
    series: [
      {
        type: "bar",
        data: coloredBarData(values, true),
        barMaxWidth: compact ? 22 : 28,
      },
    ],
  };
}

let roList: ResizeObserver[] = [];

function disposeGradeSubject() {
  chartGrade?.dispose();
  chartSubject?.dispose();
  chartGrade = null;
  chartSubject = null;
}

function disposeTag() {
  chartTag?.dispose();
  chartTag = null;
}

function disposeAll() {
  disposeGradeSubject();
  disposeTag();
}

function resizeAll() {
  chartGrade?.resize();
  chartSubject?.resize();
  chartTag?.resize();
}

function renderGradeSubjectCharts(data: MistakeStatsOverview) {
  if (!wrapGrade.value || !wrapSubject.value) return;

  const compact = narrow.value;
  const gNames = data.by_grade.map((r) => r.grade_name);
  const sNames = data.by_subject.map((r) => r.subject_name);

  wrapGrade.value.style.height = `${gNames.length ? chartHeightGrade(gNames.length) : CHART_EMPTY_H}px`;
  wrapSubject.value.style.height = `${sNames.length ? chartHeightHorizontal(sNames, compact) : CHART_EMPTY_H}px`;

  chartGrade?.dispose();
  chartSubject?.dispose();
  chartGrade = echarts.init(wrapGrade.value);
  chartSubject = echarts.init(wrapSubject.value);

  const gVals = data.by_grade.map((r) => r.mistake_count);
  chartGrade.setOption(
    gNames.length ? verticalBar(gNames, gVals, "错题数", compact) : emptyOption("当前账号在各年级暂无错题"),
    true,
  );

  const sVals = data.by_subject.map((r) => r.mistake_count);
  chartSubject.setOption(
    sNames.length ? horizontalBar(sNames, sVals, "错题数", compact) : emptyOption("当前账号在各科目暂无错题"),
    true,
  );
}

function tagEmptySubtext() {
  if (tagGradeId.value && tagSubjectId.value) return "所选年级与科目下暂无知识点标签统计";
  if (tagGradeId.value) return "所选年级下暂无知识点标签统计";
  if (tagSubjectId.value) return "所选科目下暂无知识点标签统计";
  return "当前账号暂无知识点标签统计";
}

function renderTagChart(rows: MistakeStatsTagRow[]) {
  if (!wrapTag.value) return;
  const compact = narrow.value;
  const tNames = rows.map((r) => r.tag);
  const tVals = rows.map((r) => r.mistake_count);

  wrapTag.value.style.height = `${tNames.length ? chartHeightHorizontal(tNames, compact) : CHART_EMPTY_H}px`;

  chartTag?.dispose();
  chartTag = echarts.init(wrapTag.value);
  chartTag.setOption(
    tNames.length ? horizontalBar(tNames, tVals, "错题数", compact) : emptyOption(tagEmptySubtext()),
    true,
  );
  chartTag.resize();
}

async function loadTagSubjectsForGrade(gradeId: string | null) {
  if (!gradeId) {
    try {
      tagSubjects.value = await fetchSubjects();
    } catch (e) {
      message.error((e as Error).message);
      tagSubjects.value = [];
    }
    return;
  }
  try {
    tagSubjects.value = await fetchSubjects({ grade_level_id: gradeId });
  } catch (e) {
    message.error((e as Error).message);
    tagSubjects.value = [];
  }
  if (tagSubjectId.value && !tagSubjects.value.some((s) => s.id === tagSubjectId.value)) {
    tagSubjectId.value = null;
  }
}

async function reloadTagChart() {
  tagLoading.value = true;
  try {
    const rows = await fetchMistakeStatsTags({
      grade_level_id: tagGradeId.value ?? undefined,
      subject_id: tagSubjectId.value ?? undefined,
    });
    await nextTick();
    renderTagChart(rows);
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    tagLoading.value = false;
  }
}

watch(tagGradeId, async (gradeId) => {
  await loadTagSubjectsForGrade(gradeId);
  await reloadTagChart();
});

watch(tagSubjectId, () => {
  void reloadTagChart();
});

watch(narrow, () => {
  if (!overview.value) return;
  renderGradeSubjectCharts(overview.value);
  void reloadTagChart();
});

onMounted(async () => {
  updateNarrow();
  window.addEventListener("resize", updateNarrow);
  loading.value = true;
  overview.value = null;
  try {
    const [data, gradeList] = await Promise.all([fetchMistakeStatsOverview(), fetchGrades()]);
    overview.value = data;
    grades.value = gradeList;
    await loadTagSubjectsForGrade(null);
    await nextTick();
    renderGradeSubjectCharts(data);
    renderTagChart(data.by_tag);
    roList = [];
    for (const r of [wrapGrade, wrapSubject, wrapTag]) {
      if (!r.value) continue;
      const obs = new ResizeObserver(() => resizeAll());
      obs.observe(r.value);
      roList.push(obs);
    }
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
  window.addEventListener("resize", resizeAll);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", updateNarrow);
  window.removeEventListener("resize", resizeAll);
  roList.forEach((x) => x.disconnect());
  roList = [];
  disposeAll();
});
</script>

<template>
  <div class="statistics page-root">
    <header class="page-header statistics__header">
      <h1 class="page-header__title">错题统计</h1>
      <p class="page-header__desc statistics__header-desc">
        按当前登录账号汇总全部错题；顶部为总体指标，下方按年级、科目、知识点标签三个维度展示分布。知识点标签图可按年级、科目筛选。
      </p>
      <p v-if="narrow" class="statistics__header-mobile-tip">总览指标 · 年级 / 科目 / 知识点分布</p>
    </header>

    <NSpin :show="loading">
      <div v-if="overview" class="statistics__body">
        <div class="statistics__kpis">
          <article class="statistics__kpi statistics__kpi--total surface-card">
            <NStatistic label="累计错题" tabular-nums :value="overview.total_mistake_count" />
          </article>
          <article class="statistics__kpi statistics__kpi--mastered surface-card">
            <NStatistic label="已掌握" tabular-nums :value="overview.mastered_count" />
          </article>
          <article class="statistics__kpi statistics__kpi--accent surface-card">
            <NStatistic
              label="掌握率"
              tabular-nums
              :value="overview.mastery_rate_percent"
              :precision="1"
              suffix="%"
            />
          </article>
        </div>
        <div class="statistics__grid">
          <NCard class="surface-card statistics__card statistics__panel" size="small" :bordered="false">
            <template #header>
              <div class="statistics__panel-head">
                <span class="statistics__panel-title">按年级</span>
              </div>
            </template>
            <div ref="wrapGrade" class="statistics__chart" />
          </NCard>
          <NCard class="surface-card statistics__card statistics__panel" size="small" :bordered="false">
            <template #header>
              <div class="statistics__panel-head">
                <span class="statistics__panel-title">按科目</span>
              </div>
            </template>
            <div ref="wrapSubject" class="statistics__chart" />
          </NCard>
          <NCard class="surface-card statistics__card statistics__card--tag statistics__panel" size="small" :bordered="false">
            <template #header>
              <div class="statistics__tag-head">
                <span class="statistics__panel-title">按知识点标签</span>
                <div class="statistics__tag-filters">
                  <NSelect
                    v-model:value="tagGradeId"
                    size="small"
                    :options="gradeFilterOptions"
                    placeholder="全部年级"
                    clearable
                    class="statistics__tag-select"
                  />
                  <NSelect
                    v-model:value="tagSubjectId"
                    size="small"
                    :options="subjectFilterOptions"
                    placeholder="全部科目"
                    clearable
                    class="statistics__tag-select"
                  />
                </div>
              </div>
            </template>
            <NSpin :show="tagLoading">
              <div ref="wrapTag" class="statistics__chart" />
            </NSpin>
          </NCard>
        </div>
      </div>
    </NSpin>
  </div>
</template>

<style scoped>
.statistics {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.statistics__header {
  margin-bottom: 12px;
}

.statistics__header-mobile-tip {
  display: none;
}

.statistics__body {
  max-width: 960px;
  margin: 0 auto;
  width: 100%;
}

.statistics__kpis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.statistics__kpi {
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: #fff;
}

.statistics__kpi--total {
  background: linear-gradient(145deg, #f5f7ff 0%, #ffffff 72%);
  border-color: rgba(129, 140, 248, 0.22);
}

.statistics__kpi--mastered {
  background: linear-gradient(145deg, #f8fafc 0%, #ffffff 72%);
}

.statistics__kpi--accent {
  background: linear-gradient(145deg, #ecfdf5 0%, #ffffff 72%);
  border-color: rgba(16, 185, 129, 0.22);
}

.statistics__kpi :deep(.n-statistic__label) {
  font-size: 13px;
  color: var(--app-text-muted, #64748b);
}

.statistics__kpi :deep(.n-statistic-value__content) {
  font-size: clamp(22px, 4.5vw, 28px);
  font-weight: 600;
  color: var(--app-text, #0f172a);
}

.statistics__kpi--accent :deep(.n-statistic-value__content) {
  color: #059669;
}

.statistics__grid {
  display: grid;
  gap: 20px;
  grid-template-columns: 1fr;
  width: 100%;
}

.statistics__panel-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.statistics__panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text, #0f172a);
}

.statistics__card :deep(.n-card-header) {
  padding-bottom: 6px;
}

.statistics__card :deep(.n-card__content) {
  overflow: visible;
}

.statistics__tag-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px 12px;
  width: 100%;
}

.statistics__tag-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
  flex: 1 1 auto;
}

.statistics__tag-select {
  min-width: 120px;
  width: min(160px, 42vw);
}

.statistics__chart {
  width: 100%;
  min-height: 300px;
  overflow: visible;
}

@media (min-width: 1200px) {
  .statistics__body {
    max-width: 1080px;
  }
}

@media (max-width: 768px) {
  .statistics__header {
    margin-bottom: 8px;
  }

  .statistics__header .page-header__title {
    font-size: 1.08rem;
    margin-bottom: 2px;
  }

  .statistics__header-desc {
    display: none;
  }

  .statistics__header-mobile-tip {
    display: block;
    margin: 0;
    font-size: 12px;
    line-height: 1.4;
    color: var(--app-text-muted, #64748b);
  }

  .statistics__kpis {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
    margin-bottom: 12px;
  }

  .statistics__kpi {
    padding: 10px 8px;
    border-radius: 12px;
    text-align: center;
  }

  .statistics__kpi :deep(.n-statistic) {
    align-items: center;
  }

  .statistics__kpi :deep(.n-statistic__label) {
    font-size: 11px;
    line-height: 1.3;
  }

  .statistics__kpi :deep(.n-statistic-value__content) {
    font-size: 1.35rem;
    line-height: 1.2;
  }

  .statistics__grid {
    gap: 10px;
  }

  .statistics__panel {
    border-radius: 14px;
    border: 1px solid rgba(226, 232, 240, 0.92);
    box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
    background: #fff;
  }

  .statistics__panel :deep(.n-card-header) {
    padding: 10px 12px 4px;
  }

  .statistics__panel :deep(.n-card__content) {
    padding: 4px 8px 10px !important;
  }

  .statistics__panel-head {
    gap: 7px;
  }

  .statistics__panel-title {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 12px;
    font-weight: 700;
    color: #4338ca;
    letter-spacing: 0.03em;
  }

  .statistics__panel-title::before {
    content: "";
    width: 3px;
    height: 13px;
    border-radius: 999px;
    background: linear-gradient(180deg, #a5b4fc, #6366f1);
    flex-shrink: 0;
  }

  .statistics__tag-head {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }

  .statistics__tag-filters {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    width: 100%;
  }

  .statistics__tag-select {
    width: 100% !important;
    min-width: 0;
  }

  .statistics__tag-select :deep(.n-base-selection-label) {
    overflow: visible;
    text-overflow: clip;
    white-space: nowrap;
  }

  .statistics__chart {
    min-height: 260px;
  }
}
</style>
