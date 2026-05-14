<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NFormItem,
  NImage,
  NInput,
  NRadioButton,
  NRadioGroup,
  NSpace,
  NSpin,
  NTag,
  useMessage,
} from "naive-ui";
import FormattedAnalysis from "../components/FormattedAnalysis.vue";
import type { Mistake, PracticeCheckResult, PracticeDifficulty, PracticeGenerateResult } from "../api/client";
import { checkPractice, createMistake, fetchMistake, generatePractice } from "../api/client";

const route = useRoute();
const router = useRouter();
const message = useMessage();

const id = computed(() => route.params.id as string);
const loading = ref(true);
const generating = ref(false);
const checking = ref(false);
const row = ref<Mistake | null>(null);

const difficulty = ref<PracticeDifficulty>("medium");
const question = ref<PracticeGenerateResult | null>(null);
const userAnswer = ref("");
const answerImage = ref<File | null>(null);
const answerPreviewUrl = ref<string | null>(null);
const checkResult = ref<PracticeCheckResult | null>(null);
const savingToNotebook = ref(false);
const addedToNotebook = ref(false);

const showAddToNotebook = computed(
  () => !!checkResult.value && checkResult.value.verdict !== "correct" && !addedToNotebook.value,
);

const difficultyOptions: { value: PracticeDifficulty; label: string }[] = [
  { value: "easy", label: "简单" },
  { value: "medium", label: "适中" },
  { value: "hard", label: "困难" },
  { value: "challenge", label: "挑战" },
];

const verdictMeta = computed(() => {
  const v = checkResult.value?.verdict;
  if (v === "correct") return { label: "正确", type: "success" as const };
  if (v === "partial") return { label: "部分正确", type: "warning" as const };
  return { label: "需改进", type: "error" as const };
});

const canSubmit = computed(
  () => !!question.value && (userAnswer.value.trim().length > 0 || !!answerImage.value) && !checking.value,
);

const fileInputRef = ref<HTMLInputElement | null>(null);

function revokePreview() {
  if (answerPreviewUrl.value) {
    URL.revokeObjectURL(answerPreviewUrl.value);
    answerPreviewUrl.value = null;
  }
}

function resetAnswerImage() {
  revokePreview();
  answerImage.value = null;
  if (fileInputRef.value) fileInputRef.value.value = "";
}

function onPickAnswerImage(e: Event) {
  const input = e.target as HTMLInputElement;
  const f = input.files?.[0] ?? null;
  input.value = "";
  resetAnswerImage();
  if (!f) return;
  if (!f.type.startsWith("image/")) {
    message.warning("请上传图片文件");
    return;
  }
  answerImage.value = f;
  answerPreviewUrl.value = URL.createObjectURL(f);
}

async function load() {
  loading.value = true;
  try {
    row.value = await fetchMistake(id.value);
  } catch (e) {
    message.error((e as Error).message);
    router.push(`/mistakes/${id.value}`);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
onBeforeUnmount(revokePreview);

function resetPractice() {
  question.value = null;
  userAnswer.value = "";
  resetAnswerImage();
  checkResult.value = null;
  addedToNotebook.value = false;
}

async function onGenerate() {
  generating.value = true;
  checkResult.value = null;
  addedToNotebook.value = false;
  userAnswer.value = "";
  resetAnswerImage();
  try {
    question.value = await generatePractice(id.value, difficulty.value);
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    generating.value = false;
  }
}

async function onCheck() {
  if (!question.value) return;
  if (!userAnswer.value.trim() && !answerImage.value) {
    message.warning("请填写作答或上传作答图片");
    return;
  }
  checking.value = true;
  addedToNotebook.value = false;
  try {
    checkResult.value = await checkPractice({
      mistakeId: id.value,
      questionStem: question.value.question_stem,
      referenceAnswer: question.value.reference_answer,
      referenceAnalysis: question.value.reference_analysis,
      userAnswer: userAnswer.value,
      image: answerImage.value,
    });
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    checking.value = false;
  }
}

function backToDetail() {
  router.push({ path: `/mistakes/${id.value}`, query: route.query });
}

async function addToNotebook() {
  if (!row.value || !question.value || !checkResult.value) return;
  savingToNotebook.value = true;
  try {
    const created = await createMistake({
      subject_id: row.value.subject_id,
      grade_level_id: row.value.grade_level_id,
      stem: question.value.question_stem,
      analysis: checkResult.value.explanation || question.value.reference_analysis,
      answer: checkResult.value.standard_answer || question.value.reference_answer,
    });
    addedToNotebook.value = true;
    message.success("已加入错题本");
    router.push({
      path: `/mistakes/${created.id}`,
      query: {
        grade: created.grade_level_id,
        subject: created.subject_id,
      },
    });
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    savingToNotebook.value = false;
  }
}
</script>

<template>
  <NSpin :show="loading">
    <div v-if="row" class="practice page-root" :class="{ 'page-root--fixed-actions': question && !checkResult }">
      <header class="page-header practice__header">
        <h1 class="page-header__title">举一反三</h1>
        <p class="page-header__desc">根据这道错题生成同类型练习，选择难度后答题并由 AI 批改。</p>
        <NSpace wrap :size="8" class="practice__tags">
          <NTag size="small" type="info">{{ row.subject_name ?? "—" }}</NTag>
          <NTag size="small">{{ row.grade_name ?? "—" }}</NTag>
        </NSpace>
      </header>

      <NCard class="surface-card practice__card" size="small" :bordered="false">
        <NSpin :show="generating" description="正在生成题目…">
          <NSpace vertical :size="16" style="width: 100%">
            <section class="practice__section">
              <h2 class="practice__section-title">选择难度</h2>
              <div class="practice__difficulty">
                <NRadioGroup v-model:value="difficulty" size="small" :disabled="generating || checking">
                  <NRadioButton v-for="opt in difficultyOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </NRadioButton>
                </NRadioGroup>
                <NButton type="primary" size="small" :loading="generating" :disabled="checking" @click="onGenerate">
                  {{ question ? "重新出题" : "生成题目" }}
                </NButton>
              </div>
            </section>

            <section v-if="question" class="practice__section">
              <h2 class="practice__section-title">练习题</h2>
              <div class="practice__question">
                <FormattedAnalysis :text="question.question_stem" variant="stem" empty-text="—" />
              </div>
            </section>

            <section v-if="question && !checkResult" class="practice__section">
              <h2 class="practice__section-title">你的作答</h2>
              <NSpace vertical :size="10" style="width: 100%">
                <NFormItem label="文字作答" :show-feedback="false" label-placement="top" class="practice__item">
                  <NInput
                    v-model:value="userAnswer"
                    type="textarea"
                    size="small"
                    placeholder="在此输入你的答案（可与图片作答同时使用）"
                    :autosize="{ minRows: 3, maxRows: 10 }"
                    :disabled="checking"
                  />
                </NFormItem>
                <div class="practice__upload">
                  <input ref="fileInputRef" type="file" accept="image/*" class="practice__file-input" :disabled="checking" @change="onPickAnswerImage" />
                  <NSpace align="center" wrap :size="8">
                    <NButton size="small" secondary :disabled="checking" @click="fileInputRef?.click()">上传纸面作答照片</NButton>
                    <NButton v-if="answerImage" size="small" quaternary :disabled="checking" @click="resetAnswerImage">移除图片</NButton>
                  </NSpace>
                  <NImage v-if="answerPreviewUrl" width="100%" class="practice__answer-image" :src="answerPreviewUrl" object-fit="contain" />
                </div>
              </NSpace>
            </section>

            <section v-if="checkResult" class="practice__section">
              <div class="practice__result-head">
                <h2 class="practice__section-title">批改结果</h2>
                <NTag size="small" :type="verdictMeta.type">{{ verdictMeta.label }}</NTag>
              </div>
              <div class="practice__result-block">
                <h3 class="practice__result-label">评语</h3>
                <div class="practice__result-text"><FormattedAnalysis :text="checkResult.feedback" /></div>
              </div>
              <div class="practice__result-block">
                <h3 class="practice__result-label">标准答案</h3>
                <div class="practice__result-text">{{ checkResult.standard_answer }}</div>
              </div>
              <div class="practice__result-block">
                <h3 class="practice__result-label">讲解</h3>
                <div class="practice__result-text"><FormattedAnalysis :text="checkResult.explanation" /></div>
              </div>
              <div class="app-actions app-actions--bar practice__result-actions">
                <NButton v-if="showAddToNotebook" size="small" type="primary" :loading="savingToNotebook" @click="addToNotebook">添加到错题本</NButton>
                <NButton v-else-if="addedToNotebook" size="small" disabled>已加入错题本</NButton>
                <NButton size="small" @click="resetPractice">再练一题</NButton>
              </div>
            </section>
          </NSpace>
        </NSpin>
      </NCard>

      <Teleport to="body">
        <footer v-if="question && !checkResult" class="app-actions app-actions--bar app-actions--fixed">
          <div class="app-actions--fixed-inner">
            <NButton size="small" @click="backToDetail">返回详情</NButton>
            <NButton type="primary" size="small" :loading="checking" :disabled="!canSubmit" @click="onCheck">提交批改</NButton>
          </div>
        </footer>
      </Teleport>

      <footer v-if="!question || checkResult" class="app-actions app-actions--bar practice__footer">
        <NButton size="small" @click="backToDetail">返回详情</NButton>
      </footer>
    </div>
  </NSpin>
</template>

<style scoped>
.practice__header { margin-bottom: 12px; }
.practice__tags { margin-top: 8px; }
.practice__card :deep(.n-card__content) { padding: 16px 18px; }
.practice__section-title { margin: 0 0 10px; font-size: 13px; font-weight: 600; color: #334155; }
.practice__difficulty { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.practice__question, .practice__result-text { margin: 0; padding: 12px 14px; border-radius: 10px; border: 1px solid var(--app-border); background: rgba(255, 255, 255, 0.72); font-size: 14px; line-height: 1.65; white-space: pre-wrap; word-break: break-word; color: #0f172a; }
.practice__item { margin-bottom: 0; width: 100%; }
.practice__item :deep(.n-form-item-label) { padding-bottom: 4px; font-size: 13px; font-weight: 500; }
.practice__item :deep(.n-form-item-blank) { width: 100%; }
.practice__file-input { position: absolute; width: 0; height: 0; opacity: 0; pointer-events: none; }
.practice__answer-image { margin-top: 8px; max-width: 520px; border-radius: 12px; }
.practice__result-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 10px; }
.practice__result-head .practice__section-title { margin-bottom: 0; }
.practice__result-block + .practice__result-block { margin-top: 12px; }
.practice__result-label { margin: 0 0 6px; font-size: 12px; font-weight: 600; color: var(--app-text-muted); }
.practice__result-actions { margin-top: 14px; }
.practice__footer { margin-top: 4px; }
@media (max-width: 768px) {
  .practice__difficulty { flex-direction: column; align-items: stretch; }
  .practice__difficulty :deep(.n-radio-group) { display: flex; flex-wrap: wrap; gap: 6px; }
}
</style>
