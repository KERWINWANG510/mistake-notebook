<script setup lang="ts">
import type { EChartsOption } from "echarts";
import * as echarts from "echarts";
import { NSelect, NSpin, NStatistic, useMessage } from "naive-ui";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type {
  Grade,
  MistakeStatsErrorReasonHeatmap,
  MistakeStatsOverview,
  MistakeStatsTagRow,
  ReviewStatsCharts,
  Subject,
} from "../api/client";
import {
  fetchGrades,
  fetchMistakeStatsErrorReasonHeatmap,
  fetchMistakeStatsOverview,
  fetchMistakeStatsTags,
  fetchReviewStatsCharts,
  fetchSubjects,
} from "../api/client";

const message = useMessage();
const loading = ref(true);
const tagLoading = ref(false);
const heatmapLoading = ref(false);
const overview = ref<MistakeStatsOverview | null>(null);
const reviewStats = ref<ReviewStatsCharts | null>(null);
const heatmapData = ref<MistakeStatsErrorReasonHeatmap | null>(null);

const grades = ref<Grade[]>([]);
const tagSubjects = ref<Subject[]>([]);
const tagGradeId = ref<string | null>(null);
const tagSubjectId = ref<string | null>(null);

const wrapGrade = ref<HTMLDivElement | null>(null);
const wrapSubject = ref<HTMLDivElement | null>(null);
const wrapTag = ref<HTMLDivElement | null>(null);
const wrapSource = ref<HTMLDivElement | null>(null);
const wrapHeatmap = ref<HTMLDivElement | null>(null);
const wrapReviewTrend = ref<HTMLDivElement | null>(null);
const wrapReviewResult = ref<HTMLDivElement | null>(null);

const narrow = ref(false);
function updateNarrow() {
  narrow.value = window.matchMedia("(max-width: 768px)").matches;
}

let chartGrade: ReturnType<typeof echarts.init> | null = null;
let chartSubject: ReturnType<typeof echarts.init> | null = null;
let chartTag: ReturnType<typeof echarts.init> | null = null;
let chartSource: ReturnType<typeof echarts.init> | null = null;
let chartHeatmap: ReturnType<typeof echarts.init> | null = null;
let chartReviewTrend: ReturnType<typeof echarts.init> | null = null;
let chartReviewResult: ReturnType<typeof echarts.init> | null = null;

const REVIEW_RESULT_COLORS: Record<string, string> = {
  good: "#10b981",
  again: "#f59e0b",
};

/** 知识点标签图：单独展示前 N 个，其余合并为「其他」 */
const TAG_CHART_TOP_N = 5;
const TAG_CHART_OTHER_LABEL = "其他";

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

function formatTrendDate(iso: string) {
  const p = iso.split("-");
  if (p.length === 3) return `${p[1]}-${p[2]}`;
  return iso;
}

function pieChart(
  items: { name: string; value: number; color?: string }[],
  compact: boolean,
): EChartsOption {
  const hasData = items.some((i) => i.value > 0);
  if (!hasData) {
    return emptyOption("暂无复习记录，请先在「今日复习」中完成打卡");
  }
  return {
    tooltip: {
      trigger: "item",
      formatter: "{b}：{c} 次（{d}%）",
    },
    legend: {
      bottom: 0,
      left: "center",
      textStyle: { fontSize: compact ? 11 : 12, color: "#64748b" },
    },
    series: [
      {
        type: "pie",
        radius: compact ? ["36%", "58%"] : ["40%", "64%"],
        center: ["50%", "44%"],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 4, borderColor: "#fff", borderWidth: 2 },
        label: { fontSize: compact ? 11 : 12 },
        data: items.map((i) => ({
          name: i.name,
          value: i.value,
          itemStyle: i.color ? { color: i.color } : undefined,
        })),
      },
    ],
  };
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
  chartSource?.dispose();
  chartGrade = null;
  chartSubject = null;
  chartSource = null;
}

function disposeTag() {
  chartTag?.dispose();
  chartTag = null;
}

function disposeHeatmap() {
  chartHeatmap?.dispose();
  chartHeatmap = null;
}

function disposeReviewCharts() {
  chartReviewTrend?.dispose();
  chartReviewResult?.dispose();
  chartReviewTrend = null;
  chartReviewResult = null;
}

function disposeAll() {
  disposeGradeSubject();
  disposeTag();
  disposeReviewCharts();
  disposeHeatmap();
}

function resizeAll() {
  chartGrade?.resize();
  chartSubject?.resize();
  chartSource?.resize();
  chartTag?.resize();
  chartHeatmap?.resize();
  chartReviewTrend?.resize();
  chartReviewResult?.resize();
}

function heatmapOption(data: MistakeStatsErrorReasonHeatmap, compact: boolean): EChartsOption {
  const maxVal = data.cells.length ? Math.max(...data.cells.map((c) => c[2])) : 0;
  const fontSize = compact ? 11 : 12;
  return {
    tooltip: {
      position: "top",
      formatter: (p: unknown) => {
        const item = (Array.isArray(p) ? p[0] : p) as { data?: [number, number, number] };
        const [xi, yi, val] = item?.data ?? [0, 0, 0];
        const subject = data.subject_names[xi] ?? "";
        const reason = data.reason_labels[yi] ?? "";
        return `${subject}<br/>${reason}：${val} 道`;
      },
    },
    grid: {
      left: compact ? 72 : 88,
      right: compact ? 16 : 24,
      top: compact ? 12 : 16,
      bottom: compact ? 56 : 64,
      containLabel: false,
    },
    xAxis: {
      type: "category",
      data: data.subject_names,
      splitArea: { show: true },
      axisLabel: {
        color: "#64748b",
        fontSize,
        rotate: data.subject_names.length > 5 ? 28 : 0,
        interval: 0,
      },
    },
    yAxis: {
      type: "category",
      data: data.reason_labels,
      splitArea: { show: true },
      axisLabel: { color: "#475569", fontSize },
    },
    visualMap: {
      min: 0,
      max: Math.max(maxVal, 1),
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: compact ? 4 : 8,
      itemWidth: compact ? 12 : 14,
      itemHeight: compact ? 80 : 100,
      inRange: { color: ["#eef2ff", "#a5b4fc", "#6366f1", "#4338ca"] },
      textStyle: { fontSize: 11, color: "#64748b" },
    },
    series: [
      {
        type: "heatmap",
        data: data.cells,
        label: {
          show: true,
          fontSize: compact ? 11 : 12,
          color: "#1e293b",
          formatter: (p: { data?: [number, number, number] }) => {
            const v = p?.data?.[2] ?? 0;
            return v > 0 ? String(v) : "";
          },
        },
        emphasis: {
          itemStyle: { shadowBlur: 8, shadowColor: "rgba(15, 23, 42, 0.2)" },
        },
      },
    ],
  };
}

function heatmapEmptySubtext(data: MistakeStatsErrorReasonHeatmap | null) {
  if (!data) return "加载中…";
  if (data.total_mistake_count === 0) return "当前账号暂无错题";
  if (data.annotated_mistake_count === 0) {
    return "暂无已标注错因的错题，请在录入或编辑错题时选择错因";
  }
  return "暂无足够数据生成热力图";
}

async function renderHeatmapChart(data: MistakeStatsErrorReasonHeatmap | null) {
  if (!wrapHeatmap.value) return;
  const compact = narrow.value;
  const hasCells = !!data && data.cells.length > 0;

  chartHeatmap?.dispose();
  chartHeatmap = echarts.init(wrapHeatmap.value);
  if (hasCells && data) {
    chartHeatmap.setOption(heatmapOption(data, compact), true);
  } else {
    chartHeatmap.setOption(emptyOption(heatmapEmptySubtext(data)), true);
  }
  chartHeatmap.resize();
}

async function reloadHeatmapChart() {
  heatmapLoading.value = true;
  try {
    heatmapData.value = await fetchMistakeStatsErrorReasonHeatmap();
    await nextTick();
    await renderHeatmapChart(heatmapData.value);
  } catch (e) {
    message.error((e as Error).message);
    heatmapData.value = null;
    await nextTick();
    await renderHeatmapChart(null);
  } finally {
    heatmapLoading.value = false;
  }
}

function sourceEmptySubtext() {
  return "暂无已标注错题来源的错题，请在录入或编辑时选择来源";
}

function renderReviewCharts(data: ReviewStatsCharts) {
  const compact = narrow.value;

  if (wrapReviewTrend.value) {
    const labels = data.daily_trend.map((r) => formatTrendDate(r.date));
    const vals = data.daily_trend.map((r) => r.review_count);
    const has = vals.some((v) => v > 0);
    chartReviewTrend?.dispose();
    chartReviewTrend = echarts.init(wrapReviewTrend.value);
    chartReviewTrend.setOption(
      has
        ? verticalBar(labels, vals, "复习题数", compact)
        : emptyOption("近 14 日暂无复习记录"),
      true,
    );
    chartReviewTrend.resize();
  }

  if (wrapReviewResult.value) {
    const items = data.by_result.map((r) => ({
      name: r.result_label,
      value: r.count,
      color: REVIEW_RESULT_COLORS[r.result_code],
    }));
    chartReviewResult?.dispose();
    chartReviewResult = echarts.init(wrapReviewResult.value);
    chartReviewResult.setOption(pieChart(items, compact), true);
    chartReviewResult.resize();
  }
}

function renderGradeSubjectCharts(data: MistakeStatsOverview) {
  const compact = narrow.value;

  if (wrapGrade.value) {
    const gNames = data.by_grade.map((r) => r.grade_name);
    const gVals = data.by_grade.map((r) => r.mistake_count);
    chartGrade?.dispose();
    chartGrade = echarts.init(wrapGrade.value);
    chartGrade.setOption(
      gNames.length ? verticalBar(gNames, gVals, "错题数", compact) : emptyOption("当前账号在各年级暂无错题"),
      true,
    );
    chartGrade.resize();
  }

  if (wrapSubject.value) {
    const sNames = data.by_subject.map((r) => r.subject_name);
    const sVals = data.by_subject.map((r) => r.mistake_count);
    chartSubject?.dispose();
    chartSubject = echarts.init(wrapSubject.value);
    chartSubject.setOption(
      sNames.length ? horizontalBar(sNames, sVals, "错题数", compact) : emptyOption("当前账号在各科目暂无错题"),
      true,
    );
    chartSubject.resize();
  }

  if (wrapSource.value) {
    const srcNames = data.by_source.map((r) => r.source_label);
    const srcVals = data.by_source.map((r) => r.mistake_count);
    const hasSource = srcVals.some((v) => v > 0);
    chartSource?.dispose();
    chartSource = echarts.init(wrapSource.value);
    chartSource.setOption(
      hasSource ? verticalBar(srcNames, srcVals, "错题数", compact) : emptyOption(sourceEmptySubtext()),
      true,
    );
    chartSource.resize();
  }
}

function tagEmptySubtext() {
  if (tagGradeId.value && tagSubjectId.value) return "所选年级与科目下暂无知识点标签统计";
  if (tagSubjectId.value) return "所选科目下暂无知识点标签统计";
  if (tagGradeId.value) return "所选年级下暂无知识点标签统计";
  return "当前账号暂无知识点标签统计";
}

function collapseTagRowsForChart(rows: MistakeStatsTagRow[]): MistakeStatsTagRow[] {
  if (rows.length <= TAG_CHART_TOP_N) {
    return [...rows].sort((a, b) => b.mistake_count - a.mistake_count || a.tag.localeCompare(b.tag, "zh"));
  }
  const sorted = [...rows].sort(
    (a, b) => b.mistake_count - a.mistake_count || a.tag.localeCompare(b.tag, "zh"),
  );
  const top = sorted.slice(0, TAG_CHART_TOP_N);
  const otherCount = sorted.slice(TAG_CHART_TOP_N).reduce((sum, r) => sum + r.mistake_count, 0);
  if (otherCount <= 0) return top;
  const merged = [...top, { tag: TAG_CHART_OTHER_LABEL, mistake_count: otherCount }];
  return merged.sort((a, b) => b.mistake_count - a.mistake_count);
}

function renderTagChart(rows: MistakeStatsTagRow[]) {
  if (!wrapTag.value) return;
  const compact = narrow.value;
  const displayRows = collapseTagRowsForChart(rows);
  const tNames = displayRows.map((r) => r.tag);
  const tVals = displayRows.map((r) => r.mistake_count);

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
  if (overview.value) renderGradeSubjectCharts(overview.value);
  if (reviewStats.value) renderReviewCharts(reviewStats.value);
  void reloadTagChart();
  void renderHeatmapChart(heatmapData.value);
});

onMounted(async () => {
  updateNarrow();
  window.addEventListener("resize", updateNarrow);
  loading.value = true;
  overview.value = null;
  try {
    const [data, gradeList, review] = await Promise.all([
      fetchMistakeStatsOverview(),
      fetchGrades(),
      fetchReviewStatsCharts(),
    ]);
    overview.value = data;
    reviewStats.value = review;
    grades.value = gradeList;
    await loadTagSubjectsForGrade(null);
    await nextTick();
    renderGradeSubjectCharts(data);
    renderReviewCharts(review);
    renderTagChart(data.by_tag);
    await reloadHeatmapChart();
    roList = [];
    for (const r of [wrapGrade, wrapSubject, wrapSource, wrapTag, wrapHeatmap, wrapReviewTrend, wrapReviewResult]) {
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
    <header class="statistics-hero">
      <div class="statistics-hero__text">
        <h1 class="statistics-hero__title">错题统计</h1>
        <p class="statistics-hero__desc">
          汇总当前账号的错题掌握、复习打卡与多维分布；知识点标签支持按年级、科目筛选。
        </p>
      </div>
      <div class="statistics-hero__chips" aria-label="统计模块">
        <span class="statistics-hero__chip">错题总览</span>
        <span class="statistics-hero__chip">今日复习</span>
        <span class="statistics-hero__chip">分布图表</span>
      </div>
    </header>

    <NSpin :show="loading">
      <div v-if="overview" class="statistics-layout">
        <section class="statistics-section" aria-labelledby="stats-overview-heading">
          <div class="statistics-section__head">
            <h2 id="stats-overview-heading" class="statistics-section__title">错题总览</h2>
          </div>
          <div class="statistics-kpi-grid statistics-kpi-grid--3">
            <article class="statistics-kpi statistics-kpi--total">
              <NStatistic label="累计错题" tabular-nums :value="overview.total_mistake_count" />
            </article>
            <article class="statistics-kpi statistics-kpi--mastered">
              <NStatistic label="已掌握" tabular-nums :value="overview.mastered_count" />
            </article>
            <article class="statistics-kpi statistics-kpi--accent">
              <NStatistic
                label="掌握率"
                tabular-nums
                :value="overview.mastery_rate_percent"
                :precision="1"
                suffix="%"
              />
            </article>
          </div>
        </section>

        <section v-if="reviewStats" class="statistics-section" aria-labelledby="stats-review-heading">
          <div class="statistics-section__head">
            <h2 id="stats-review-heading" class="statistics-section__title">今日复习</h2>
            <p class="statistics-section__hint">近 14 日趋势与打卡结果</p>
          </div>
          <div class="statistics-kpi-grid statistics-kpi-grid--4">
            <article class="statistics-kpi statistics-kpi--review">
              <NStatistic label="连续打卡" tabular-nums :value="reviewStats.streak_days" suffix=" 天" />
            </article>
            <article class="statistics-kpi statistics-kpi--review">
              <NStatistic label="今日进度" tabular-nums>
                <span class="statistics-kpi__value-inline">
                  {{ reviewStats.today_completed }} / {{ reviewStats.daily_target }}
                </span>
              </NStatistic>
            </article>
            <article class="statistics-kpi statistics-kpi--review">
              <NStatistic label="待复习（今日到期）" tabular-nums :value="reviewStats.due_total" />
            </article>
            <article class="statistics-kpi statistics-kpi--review">
              <NStatistic label="累计复习次数" tabular-nums :value="reviewStats.total_reviewed_all_time" />
            </article>
          </div>
          <div class="statistics-chart-grid statistics-chart-grid--2">
            <article class="statistics-panel">
              <header class="statistics-panel__head">
                <span class="statistics-panel__title">近 14 日复习题数</span>
              </header>
              <div class="statistics-panel__body">
                <div ref="wrapReviewTrend" class="statistics-chart" />
              </div>
            </article>
            <article class="statistics-panel">
              <header class="statistics-panel__head">
                <span class="statistics-panel__title">复习结果分布</span>
              </header>
              <div class="statistics-panel__body">
                <div ref="wrapReviewResult" class="statistics-chart" />
              </div>
            </article>
          </div>
        </section>

        <section class="statistics-section" aria-labelledby="stats-dist-heading">
          <div class="statistics-section__head">
            <h2 id="stats-dist-heading" class="statistics-section__title">错题分布</h2>
            <p class="statistics-section__hint">年级、科目、来源、错因与知识点</p>
          </div>
          <div class="statistics-chart-grid statistics-chart-grid--2">
            <article class="statistics-panel">
              <header class="statistics-panel__head">
                <span class="statistics-panel__title">按年级</span>
              </header>
              <div class="statistics-panel__body">
                <div ref="wrapGrade" class="statistics-chart" />
              </div>
            </article>
            <article class="statistics-panel">
              <header class="statistics-panel__head">
                <span class="statistics-panel__title">按科目</span>
              </header>
              <div class="statistics-panel__body">
                <div ref="wrapSubject" class="statistics-chart" />
              </div>
            </article>
            <article class="statistics-panel">
              <header class="statistics-panel__head">
                <span class="statistics-panel__title">按错题来源</span>
              </header>
              <div class="statistics-panel__body">
                <div ref="wrapSource" class="statistics-chart" />
              </div>
            </article>
            <article class="statistics-panel">
              <header class="statistics-panel__head statistics-panel__head--stack">
                <span class="statistics-panel__title">错因 × 科目</span>
                <span v-if="heatmapData" class="statistics-panel__hint">
                  已标注 {{ heatmapData.annotated_mistake_count }} / {{ heatmapData.total_mistake_count }} 道
                </span>
              </header>
              <div class="statistics-panel__body">
                <NSpin :show="heatmapLoading">
                  <div ref="wrapHeatmap" class="statistics-chart" />
                </NSpin>
              </div>
            </article>
            <article class="statistics-panel statistics-panel--wide">
              <header class="statistics-panel__head statistics-panel__head--tag">
                <span class="statistics-panel__title">按知识点标签</span>
                <div class="statistics-panel__filters">
                  <NSelect
                    v-model:value="tagGradeId"
                    size="small"
                    :options="gradeFilterOptions"
                    placeholder="全部年级"
                    clearable
                    class="statistics-panel__select"
                  />
                  <NSelect
                    v-model:value="tagSubjectId"
                    size="small"
                    :options="subjectFilterOptions"
                    placeholder="全部科目"
                    clearable
                    class="statistics-panel__select"
                  />
                </div>
              </header>
              <div class="statistics-panel__body">
                <NSpin :show="tagLoading">
                  <div ref="wrapTag" class="statistics-chart" />
                </NSpin>
              </div>
            </article>
          </div>
        </section>
      </div>
    </NSpin>
  </div>
</template>

<style scoped>
.statistics {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

/* 页头 */
.statistics-hero {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px 20px;
  margin-bottom: 20px;
  padding: 18px 20px;
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(255, 255, 255, 0.98) 52%);
  box-shadow: var(--app-shadow, 0 4px 24px rgba(15, 23, 42, 0.06));
}

.statistics-hero__title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.statistics-hero__desc {
  margin: 8px 0 0;
  max-width: 52em;
  font-size: 13px;
  line-height: 1.55;
  color: var(--app-text-muted, #64748b);
}

.statistics-hero__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-self: center;
}

.statistics-hero__chip {
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: #4338ca;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.18);
}

.statistics-layout {
  max-width: 1120px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

/* 分区 */
.statistics-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.statistics-section__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 6px 12px;
}

.statistics-section__title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.01em;
  display: flex;
  align-items: center;
  gap: 10px;
}

.statistics-section__title::before {
  content: "";
  width: 4px;
  height: 1.1em;
  border-radius: 4px;
  background: linear-gradient(180deg, #818cf8, #6366f1);
  flex-shrink: 0;
}

.statistics-section__hint {
  margin: 0;
  font-size: 12px;
  color: var(--app-text-subtle, #94a3b8);
}

/* KPI */
.statistics-kpi-grid {
  display: grid;
  gap: 12px;
}

.statistics-kpi-grid--3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.statistics-kpi-grid--4 {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.statistics-kpi {
  position: relative;
  padding: 16px 18px;
  border-radius: 14px;
  border: 1px solid rgba(226, 232, 240, 0.92);
  background: #fff;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
  overflow: hidden;
  transition:
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.statistics-kpi:hover {
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.1);
  transform: translateY(-1px);
}

.statistics-kpi::after {
  content: "";
  position: absolute;
  top: 0;
  right: 0;
  width: 72px;
  height: 72px;
  border-radius: 0 0 0 72px;
  opacity: 0.35;
  pointer-events: none;
}

.statistics-kpi--total {
  background: linear-gradient(145deg, #f5f7ff 0%, #fff 70%);
  border-color: rgba(129, 140, 248, 0.25);
}

.statistics-kpi--total::after {
  background: radial-gradient(circle at 100% 0%, #818cf8 0%, transparent 70%);
}

.statistics-kpi--mastered {
  background: linear-gradient(145deg, #f8fafc 0%, #fff 70%);
}

.statistics-kpi--mastered::after {
  background: radial-gradient(circle at 100% 0%, #94a3b8 0%, transparent 70%);
}

.statistics-kpi--accent {
  background: linear-gradient(145deg, #ecfdf5 0%, #fff 70%);
  border-color: rgba(16, 185, 129, 0.22);
}

.statistics-kpi--accent::after {
  background: radial-gradient(circle at 100% 0%, #34d399 0%, transparent 70%);
}

.statistics-kpi--review {
  background: linear-gradient(145deg, #faf5ff 0%, #fff 72%);
  border-color: rgba(139, 92, 246, 0.2);
}

.statistics-kpi--review::after {
  background: radial-gradient(circle at 100% 0%, #a78bfa 0%, transparent 70%);
}

.statistics-kpi :deep(.n-statistic__label) {
  font-size: 13px;
  font-weight: 500;
  color: var(--app-text-muted, #64748b);
}

.statistics-kpi :deep(.n-statistic-value__content) {
  font-size: clamp(1.35rem, 4vw, 1.75rem);
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.statistics-kpi--accent :deep(.n-statistic-value__content) {
  color: #059669;
}

.statistics-kpi--review :deep(.n-statistic-value__content) {
  color: #4f46e5;
}

.statistics-kpi__value-inline {
  font-size: clamp(1.2rem, 3.5vw, 1.5rem);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #4f46e5;
  line-height: 1.2;
}

/* 图表区 */
.statistics-chart-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: 1fr;
}

.statistics-chart-grid--2 {
  grid-template-columns: 1fr;
}

@media (min-width: 769px) {
  .statistics-chart-grid--2 {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .statistics-panel--wide {
    grid-column: 1 / -1;
  }
}

.statistics-panel {
  min-width: 0;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.92);
  background: #fff;
  box-shadow: 0 2px 14px rgba(15, 23, 42, 0.05);
  overflow: hidden;
}

.statistics-panel__head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px 10px;
  border-bottom: 1px solid rgba(241, 245, 249, 0.95);
  background: linear-gradient(180deg, #fafbff 0%, #fff 100%);
}

.statistics-panel__head--stack {
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.statistics-panel__head--tag {
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 10px 12px;
}

.statistics-panel__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
  letter-spacing: -0.01em;
}

.statistics-panel__title::before {
  content: "";
  width: 3px;
  height: 14px;
  border-radius: 999px;
  background: linear-gradient(180deg, #a5b4fc, #6366f1);
  flex-shrink: 0;
}

.statistics-panel__hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--app-text-muted, #64748b);
  padding-left: 11px;
}

.statistics-panel__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.statistics-panel__select {
  min-width: 120px;
  width: min(168px, 42vw);
}

.statistics-panel__body {
  padding: 8px 12px 14px;
}

.statistics-panel__body :deep(.n-spin-container),
.statistics-panel__body :deep(.n-spin-content) {
  width: 100%;
}

.statistics-chart {
  width: 100%;
  height: 360px;
  min-height: 360px;
  max-height: 360px;
  box-sizing: border-box;
  overflow: hidden;
}

@media (max-width: 768px) {
  .statistics-hero {
    padding: 14px 16px;
    margin-bottom: 14px;
  }

  .statistics-hero__title {
    font-size: 1.12rem;
  }

  .statistics-hero__desc {
    font-size: 12px;
    margin-top: 6px;
  }

  .statistics-hero__chips {
    width: 100%;
  }

  .statistics-layout {
    gap: 20px;
  }

  .statistics-section__title {
    font-size: 0.95rem;
  }

  .statistics-kpi-grid--3 {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }

  .statistics-kpi-grid--4 {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .statistics-kpi {
    padding: 10px 8px;
    text-align: center;
    border-radius: 12px;
  }

  .statistics-kpi:hover {
    transform: none;
  }

  .statistics-kpi::after {
    display: none;
  }

  .statistics-kpi :deep(.n-statistic) {
    align-items: center;
  }

  .statistics-kpi :deep(.n-statistic__label) {
    font-size: 11px;
    line-height: 1.3;
  }

  .statistics-kpi :deep(.n-statistic-value__content) {
    font-size: 1.25rem;
  }

  .statistics-kpi__value-inline {
    font-size: 1.15rem;
  }

  .statistics-chart-grid {
    gap: 10px;
  }

  .statistics-panel__head {
    padding: 10px 12px 8px;
  }

  .statistics-panel__head--tag {
    flex-direction: column;
    align-items: stretch;
  }

  .statistics-panel__filters {
    display: grid;
    grid-template-columns: 1fr 1fr;
    width: 100%;
  }

  .statistics-panel__select {
    width: 100% !important;
    min-width: 0;
  }

  .statistics-panel__body {
    padding: 4px 8px 10px;
  }

  .statistics-chart {
    height: 280px;
    min-height: 280px;
    max-height: 280px;
  }
}
</style>
