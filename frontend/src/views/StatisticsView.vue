<script setup lang="ts">
import type { EChartsOption } from "echarts";
import * as echarts from "echarts";
import { NCard, NSpin, NStatistic, useMessage } from "naive-ui";
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import type { MistakeStatsOverview } from "../api/client";
import { fetchMistakeStatsOverview } from "../api/client";

const message = useMessage();
const loading = ref(true);
const overview = ref<MistakeStatsOverview | null>(null);

const wrapGrade = ref<HTMLDivElement | null>(null);
const wrapSubject = ref<HTMLDivElement | null>(null);
const wrapTag = ref<HTMLDivElement | null>(null);

let chartGrade: ReturnType<typeof echarts.init> | null = null;
let chartSubject: ReturnType<typeof echarts.init> | null = null;
let chartTag: ReturnType<typeof echarts.init> | null = null;

const CHART_GRADE_MIN = 340;
const CHART_EMPTY_H = 300;
const CHART_ROW_H = 44;

function chartHeightGrade(count: number) {
  return Math.min(440, Math.max(CHART_GRADE_MIN, 280 + count * 30));
}

/** 横向柱状图：按条数与最长标签估算高度，避免文字被裁切 */
function chartHeightHorizontal(names: string[]) {
  const n = Math.max(names.length, 1);
  const maxLen = names.length ? Math.max(...names.map((s) => s.length)) : 0;
  const extra = maxLen > 14 ? Math.min(140, (maxLen - 14) * 7) : 0;
  return Math.min(760, Math.max(340, 112 + n * CHART_ROW_H + extra));
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

function verticalBar(names: string[], values: number[], yName: string): EChartsOption {
  const rotate = names.length > 8 ? 36 : names.length > 4 ? 26 : 0;
  const bottom = rotate ? "26%" : names.length > 6 ? "20%" : "16%";
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
      top: "12%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: names,
      axisLabel: {
        rotate,
        interval: 0,
        color: "#64748b",
        fontSize: 12,
        lineHeight: 18,
        hideOverlap: false,
      },
    },
    yAxis: {
      type: "value",
      name: yName,
      nameTextStyle: { color: "#64748b", fontSize: 12 },
      axisLabel: { color: "#64748b", fontSize: 12 },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    series: [
      {
        type: "bar",
        data: values,
        barMaxWidth: 44,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "#818cf8" },
            { offset: 1, color: "#6366f1" },
          ]),
          borderRadius: [6, 6, 0, 0],
        },
      },
    ],
  };
}

/** 横向图右侧：数值刻度 + 留白，避免大数字或千分位被裁切 */
function horizontalGridRightPx(values: number[]) {
  const maxVal = values.length ? Math.max(0, ...values) : 0;
  const digitLen = Math.max(1, String(Math.ceil(maxVal)).length);
  return Math.min(168, Math.max(96, 64 + digitLen * 14));
}

function horizontalBar(names: string[], values: number[], xName: string): EChartsOption {
  const gridRight = horizontalGridRightPx(values);
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
      left: 12,
      right: gridRight,
      bottom: 44,
      top: 44,
      containLabel: true,
    },
    xAxis: {
      type: "value",
      name: xName,
      nameLocation: "middle",
      nameGap: 28,
      nameTextStyle: { color: "#64748b", fontSize: 12 },
      axisLabel: {
        color: "#64748b",
        fontSize: 12,
        margin: 10,
        hideOverlap: false,
      },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    yAxis: {
      type: "category",
      data: names,
      axisLabel: {
        color: "#475569",
        fontSize: 12,
        lineHeight: 20,
        margin: 14,
        width: 280,
        overflow: "break",
      },
      inverse: true,
    },
    series: [
      {
        type: "bar",
        data: values,
        barMaxWidth: 28,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: "#34d399" },
            { offset: 1, color: "#10b981" },
          ]),
          borderRadius: [0, 6, 6, 0],
        },
      },
    ],
  };
}

let roList: ResizeObserver[] = [];

function disposeAll() {
  chartGrade?.dispose();
  chartSubject?.dispose();
  chartTag?.dispose();
  chartGrade = null;
  chartSubject = null;
  chartTag = null;
}

function resizeAll() {
  chartGrade?.resize();
  chartSubject?.resize();
  chartTag?.resize();
}

function renderCharts(data: MistakeStatsOverview) {
  disposeAll();
  if (!wrapGrade.value || !wrapSubject.value || !wrapTag.value) return;

  const gNames = data.by_grade.map((r) => r.grade_name);
  const sNames = data.by_subject.map((r) => r.subject_name);
  const tNames = data.by_tag.map((r) => r.tag);

  wrapGrade.value.style.height = `${gNames.length ? chartHeightGrade(gNames.length) : CHART_EMPTY_H}px`;
  wrapSubject.value.style.height = `${sNames.length ? chartHeightHorizontal(sNames) : CHART_EMPTY_H}px`;
  wrapTag.value.style.height = `${tNames.length ? chartHeightHorizontal(tNames) : CHART_EMPTY_H}px`;

  chartGrade = echarts.init(wrapGrade.value);
  chartSubject = echarts.init(wrapSubject.value);
  chartTag = echarts.init(wrapTag.value);

  const gVals = data.by_grade.map((r) => r.mistake_count);
  chartGrade.setOption(
    gNames.length ? verticalBar(gNames, gVals, "错题数") : emptyOption("当前账号在各年级暂无错题"),
    true,
  );

  const sVals = data.by_subject.map((r) => r.mistake_count);
  chartSubject.setOption(
    sNames.length ? horizontalBar(sNames, sVals, "错题数") : emptyOption("当前账号在各科目暂无错题"),
    true,
  );

  const tVals = data.by_tag.map((r) => r.mistake_count);
  chartTag.setOption(
    tNames.length ? horizontalBar(tNames, tVals, "错题数") : emptyOption("当前账号暂无知识点标签统计"),
    true,
  );

  resizeAll();
}

onMounted(async () => {
  loading.value = true;
  overview.value = null;
  try {
    const data = await fetchMistakeStatsOverview();
    overview.value = data;
    await nextTick();
    renderCharts(data);
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
      <p class="page-header__desc">
        按当前登录账号汇总全部错题；顶部为总体指标，下方按年级、科目、知识点标签三个维度展示分布。图表纵向排列，便于阅读完整标签。
      </p>
    </header>

    <NSpin :show="loading">
      <div v-if="overview" class="statistics__body">
        <div class="statistics__kpis">
          <NCard class="surface-card statistics__kpi" size="small" :bordered="false">
            <NStatistic label="累计错题数量" tabular-nums :value="overview.total_mistake_count" />
          </NCard>
          <NCard class="surface-card statistics__kpi" size="small" :bordered="false">
            <NStatistic label="已掌握数量" tabular-nums :value="overview.mastered_count" />
          </NCard>
          <NCard class="surface-card statistics__kpi statistics__kpi--accent" size="small" :bordered="false">
            <NStatistic
              label="掌握率"
              tabular-nums
              :value="overview.mastery_rate_percent"
              :precision="1"
              suffix="%"
            />
          </NCard>
        </div>
        <div class="statistics__grid">
          <NCard class="surface-card statistics__card" title="按年级" size="small" :bordered="false">
            <div ref="wrapGrade" class="statistics__chart" />
          </NCard>
          <NCard class="surface-card statistics__card" title="按科目" size="small" :bordered="false">
            <div ref="wrapSubject" class="statistics__chart" />
          </NCard>
          <NCard class="surface-card statistics__card" title="按知识点标签" size="small" :bordered="false">
            <div ref="wrapTag" class="statistics__chart" />
          </NCard>
        </div>
      </div>
    </NSpin>
  </div>
</template>

<style scoped>
.statistics__header {
  margin-bottom: 12px;
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

@media (min-width: 1200px) {
  .statistics__body {
    max-width: 1080px;
  }
}

.statistics__card :deep(.n-card-header) {
  padding-bottom: 6px;
}

/* 避免卡片内容区裁切 ECharts 画布边缘的轴文字 */
.statistics__card :deep(.n-card__content) {
  overflow: visible;
}

.statistics__chart {
  width: 100%;
  min-height: 300px;
  overflow: visible;
}
</style>
