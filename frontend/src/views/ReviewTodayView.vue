<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NProgress,
  NSelect,
  NSpace,
  NSpin,
  NTag,
  useMessage,
} from "naive-ui";
import FormattedAnalysis from "../components/FormattedAnalysis.vue";
import type { Grade, ReviewToday, ReviewTodayItem, SubjectMistakeSummary } from "../api/client";
import {
  fetchGrades,
  fetchReviewSettings,
  fetchReviewToday,
  fetchSubjectMistakeSummary,
  submitReviewRecord,
  updateReviewSettings,
} from "../api/client";
import { useAuthStore } from "../stores/auth";
import { inferCurrentGradeLevel, resolveGradeByLevel } from "../utils/inferGrade";

const router = useRouter();
const route = useRoute();
const message = useMessage();
const auth = useAuthStore();

const loading = ref(true);
const submitting = ref(false);
const data = ref<ReviewToday | null>(null);
const grades = ref<Grade[]>([]);
const subjects = ref<SubjectMistakeSummary[]>([]);
const gradeId = ref<string | null>(null);
const subjectId = ref<string | null>(null);
const queueIndex = ref(0);
const showSolution = ref(false);

const current = computed(() => data.value?.items[queueIndex.value] ?? null);

const progressPercent = computed(() => {
  if (!data.value?.daily_target) return 0;
  return Math.min(100, Math.round((data.value.today_completed / data.value.daily_target) * 100));
});

const queueRemain = computed(() => {
  if (!data.value) return 0;
  return Math.max(0, data.value.items.length - queueIndex.value);
});

const gradeOptions = computed(() =>
  grades.value.map((g) => ({ label: g.name, value: g.id })),
);

const subjectOptions = computed(() =>
  subjects.value.map((s) => ({ label: s.subject_name, value: s.subject_id })),
);

async function loadSubjects() {
  if (!gradeId.value) {
    subjects.value = [];
    return;
  }
  subjects.value = await fetchSubjectMistakeSummary(gradeId.value);
}

async function loadToday() {
  loading.value = true;
  try {
    data.value = await fetchReviewToday({
      grade_level_id: gradeId.value,
      subject_id: subjectId.value,
    });
    queueIndex.value = 0;
    showSolution.value = false;
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}

async function persistScope() {
  try {
    await updateReviewSettings({
      review_grade_level_id: gradeId.value,
      review_subject_id: subjectId.value,
    });
  } catch {
    /* 范围保存失败不阻断复习 */
  }
}

async function onScopeChange() {
  await persistScope();
  await loadSubjects();
  await loadToday();
}

onMounted(async () => {
  try {
    grades.value = await fetchGrades();
    if (!auth.me) await auth.fetchMe();
    const settings = await fetchReviewSettings();
    const inferred = resolveGradeByLevel(inferCurrentGradeLevel(auth.me), grades.value);
    gradeId.value =
      settings.review_grade_level_id ?? inferred?.id ?? grades.value[0]?.id ?? null;
    subjectId.value = settings.review_subject_id;
    await loadSubjects();
    if (route.query.mistake_id) {
      await loadToday();
      const mid = String(route.query.mistake_id);
      const idx = data.value?.items.findIndex((i) => i.mistake_id === mid) ?? -1;
      if (idx >= 0) queueIndex.value = idx;
    } else {
      await loadToday();
    }
  } catch (e) {
    message.error((e as Error).message);
    loading.value = false;
  }
});

async function onGradeChange(val: string | null) {
  gradeId.value = val;
  subjectId.value = null;
  await onScopeChange();
}

async function onSubjectChange(val: string | null) {
  subjectId.value = val;
  await onScopeChange();
}

function nextCard() {
  showSolution.value = false;
  if (data.value && queueIndex.value < data.value.items.length - 1) {
    queueIndex.value += 1;
  } else {
    queueIndex.value = data.value?.items.length ?? 0;
  }
}

async function record(result: "good" | "again", item: ReviewTodayItem) {
  submitting.value = true;
  try {
    const res = await submitReviewRecord({
      mistake_id: item.mistake_id,
      result,
      grade_level_id: gradeId.value,
      subject_id: subjectId.value,
    });
    if (data.value) {
      data.value.today_completed = res.today_completed;
      data.value.streak_days = res.streak_days;
      data.value.due_total = Math.max(0, data.value.due_total - 1);
    }
    message.success(result === "good" ? "已记录：掌握良好" : "已记录：需要再练");
    nextCard();
    if (data.value && queueIndex.value >= data.value.items.length) {
      await loadToday();
    }
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    submitting.value = false;
  }
}

function goPractice(item: ReviewTodayItem) {
  router.push({
    path: `/mistakes/${item.mistake_id}/practice`,
    query: {
      from: "review",
      grade: item.grade_level_id,
      subject: item.subject_id,
      mistake_id: item.mistake_id,
    },
  });
}

function openDetail(item: ReviewTodayItem) {
  router.push({
    path: `/mistakes/${item.mistake_id}`,
    query: { grade: item.grade_level_id, subject: item.subject_id },
  });
}
</script>

<template>
  <NSpin :show="loading">
    <div class="review-today page-root" :class="{ 'page-root--fixed-actions': !!current }">
      <header class="page-header review-today__header">
        <h1 class="page-header__title">今日复习</h1>
        <p class="page-header__desc">
          先看原题回忆，再点开「显示解析」核对思路与答案。每完成一题底部操作即计入今日打卡。
        </p>
        <ul class="review-today__action-tips" aria-label="底部操作说明">
          <li><span class="review-today__action-name">再练练</span>：仍不熟，记入复习并约明天再复习本题。</li>
          <li><span class="review-today__action-name">举一反三</span>：跳转同类型 AI 练习（不改变今日复习记录，练完可返回继续）。</li>
          <li><span class="review-today__action-name">会了</span>：已掌握，记入复习并按间隔推迟下次复习（约 3 天起）。</li>
        </ul>
      </header>

      <section class="review-today__stats">
        <NCard class="surface-card review-today__stat" size="small" :bordered="false">
          <div class="review-today__stat-label">连续打卡</div>
          <div class="review-today__stat-value">{{ data?.streak_days ?? 0 }}<span class="review-today__stat-unit">天</span></div>
        </NCard>
        <NCard class="surface-card review-today__stat" size="small" :bordered="false">
          <div class="review-today__stat-label">今日进度</div>
          <div class="review-today__stat-value">
            {{ data?.today_completed ?? 0 }}/{{ data?.daily_target ?? 10 }}
          </div>
          <NProgress type="line" :percentage="progressPercent" :show-indicator="false" :height="6" />
        </NCard>
        <NCard class="surface-card review-today__stat" size="small" :bordered="false">
          <div class="review-today__stat-label">待复习</div>
          <div class="review-today__stat-value">{{ data?.due_total ?? 0 }}<span class="review-today__stat-unit">题</span></div>
        </NCard>
      </section>

      <NCard class="surface-card review-today__filters" size="small" :bordered="false">
        <div class="review-today__filter-grid">
          <div class="review-today__filter-field">
            <span class="review-today__filter-k">年级</span>
            <NSelect
              :value="gradeId"
              size="small"
              :options="gradeOptions"
              placeholder="选择年级"
              clearable
              @update:value="onGradeChange"
            />
          </div>
          <div class="review-today__filter-field">
            <span class="review-today__filter-k">科目</span>
            <NSelect
              :value="subjectId"
              size="small"
              :options="subjectOptions"
              placeholder="全部科目"
              clearable
              :disabled="!gradeId"
              @update:value="onSubjectChange"
            />
          </div>
        </div>
      </NCard>

      <NCard v-if="current" class="surface-card review-today__card" size="small" :bordered="false">
        <div class="review-today__card-head">
          <NSpace :size="6" wrap>
            <NTag size="small" type="info">{{ current.subject_name ?? "—" }}</NTag>
            <NTag size="small">{{ current.grade_name ?? "—" }}</NTag>
            <NTag v-if="current.is_mastered" size="small" type="success">已掌握</NTag>
          </NSpace>
          <span class="review-today__queue-tip">本批剩余 {{ queueRemain }} 题</span>
        </div>

        <section class="review-today__block">
          <h2 class="review-today__block-title">原题</h2>
          <div class="review-today__stem">
            <FormattedAnalysis :text="current.stem_preview" variant="stem" empty-text="—" />
          </div>
          <NButton size="tiny" quaternary @click="openDetail(current)">查看完整详情</NButton>
        </section>

        <section class="review-today__block">
          <div class="review-today__block-head">
            <h2 class="review-today__block-title">解析与答案</h2>
            <NButton size="tiny" secondary @click="showSolution = !showSolution">
              {{ showSolution ? "收起" : "显示解析" }}
            </NButton>
          </div>
          <div v-show="showSolution" class="review-today__solution">
            <h3 class="review-today__solution-k">解题思路</h3>
            <FormattedAnalysis :text="current.analysis" />
            <h3 class="review-today__solution-k">答案</h3>
            <FormattedAnalysis :text="current.answer" variant="stem" />
          </div>
          <p v-if="!showSolution" class="review-today__hint">先回忆解题过程，再点开查看解析。</p>
        </section>

        <p class="review-today__encourage">建议：若仍不熟，可点「举一反三」做同类型练习。</p>
      </NCard>

      <NCard v-else-if="!loading" class="surface-card review-today__empty" size="small" :bordered="false">
        <p class="review-today__empty-title">
          {{ (data?.due_total ?? 0) > 0 ? "本批已完成" : "暂无待复习错题" }}
        </p>
        <p class="review-today__empty-desc">
          <template v-if="(data?.due_total ?? 0) > 0">
            仍有 {{ data?.due_total }} 道到期题未在本批展示（受每日目标限制），可明日继续或调整筛选。
          </template>
          <template v-else>
            仅显示已到期且符合筛选的错题（下次复习日不晚于今天）；默认不含已掌握题，可在「系统设置 → 通用设置」开启。请确认年级、科目与错题本一致。
          </template>
        </p>
        <div class="app-actions review-today__empty-actions">
          <NButton size="small" @click="router.push('/mistakes')">错题本</NButton>
          <NButton size="small" type="primary" @click="loadToday">刷新队列</NButton>
        </div>
      </NCard>

      <Teleport to="body">
        <footer v-if="current" class="app-actions app-actions--bar app-actions--fixed">
          <div class="app-actions--fixed-inner">
            <NButton size="small" :disabled="submitting" @click="record('again', current)">再练练</NButton>
            <NButton size="small" secondary :disabled="submitting" @click="goPractice(current)">举一反三</NButton>
            <NButton size="small" type="primary" :loading="submitting" @click="record('good', current)">会了</NButton>
          </div>
        </footer>
      </Teleport>
    </div>
  </NSpin>
</template>

<style scoped>
.review-today__header {
  margin-bottom: 12px;
}

.review-today__action-tips {
  margin: 8px 0 0;
  padding: 10px 12px;
  list-style: none;
  border-radius: 10px;
  border: 1px solid var(--app-border, rgba(226, 232, 240, 0.92));
  background: rgba(255, 255, 255, 0.55);
  font-size: 12px;
  line-height: 1.55;
  color: var(--app-text-muted, #64748b);
}

.review-today__action-tips li + li {
  margin-top: 6px;
}

.review-today__action-name {
  font-weight: 600;
  color: #4338ca;
}

.review-today__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.review-today__stat :deep(.n-card__content) {
  padding: 12px 14px;
}

.review-today__stat-label {
  font-size: 12px;
  color: var(--app-text-muted, #64748b);
  margin-bottom: 4px;
}

.review-today__stat-value {
  font-size: 1.35rem;
  font-weight: 700;
  color: #4338ca;
  line-height: 1.2;
}

.review-today__stat-unit {
  font-size: 0.85rem;
  font-weight: 500;
  margin-left: 2px;
  color: var(--app-text-muted, #64748b);
}

.review-today__filters {
  margin-bottom: 12px;
}

.review-today__filters :deep(.n-card__content) {
  padding: 12px 14px;
}

.review-today__filter-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 12px;
  width: 100%;
}

.review-today__filter-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.review-today__filter-k {
  font-size: 13px;
  font-weight: 500;
  color: #334155;
}

.review-today__card :deep(.n-card__content) {
  padding: 14px 16px;
}

.review-today__card-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}

.review-today__queue-tip {
  font-size: 12px;
  color: var(--app-text-muted, #64748b);
}

.review-today__block + .review-today__block {
  margin-top: 14px;
}

.review-today__block-title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.review-today__block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.review-today__block-head .review-today__block-title {
  margin-bottom: 0;
}

.review-today__stem,
.review-today__solution {
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--app-border, rgba(226, 232, 240, 0.92));
  background: rgba(255, 255, 255, 0.72);
  font-size: 14px;
  line-height: 1.65;
}

.review-today__solution-k {
  margin: 10px 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--app-text-muted, #64748b);
}

.review-today__solution-k:first-child {
  margin-top: 0;
}

.review-today__hint,
.review-today__encourage {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--app-text-muted, #64748b);
  line-height: 1.5;
}

.review-today__empty {
  text-align: center;
}

.review-today__empty :deep(.n-card__content) {
  padding: 24px 16px;
}

.review-today__empty-title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

.review-today__empty-desc {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--app-text-muted, #64748b);
  line-height: 1.55;
}

.review-today__empty-actions {
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .review-today__stats {
    grid-template-columns: 1fr;
  }

  .review-today.page-root--fixed-actions {
    padding-bottom: calc(72px + env(safe-area-inset-bottom, 0px));
  }
}
</style>
