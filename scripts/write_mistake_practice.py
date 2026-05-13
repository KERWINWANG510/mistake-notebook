# -*- coding: utf-8 -*-
"""Regenerate MistakePractice.vue with correct UTF-8 Chinese. Run: python scripts/write_mistake_practice.py"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "src" / "views" / "MistakePractice.vue"

L = {
    "easy": "\u7b80\u5355",
    "medium": "\u9002\u4e2d",
    "hard": "\u56f0\u96be",
    "challenge": "\u6311\u6218",
    "correct": "\u6b63\u786e",
    "partial": "\u90e8\u5206\u6b63\u786e",
    "wrong": "\u9700\u6539\u8fdb",
    "warn_img": "\u8bf7\u4e0a\u4f20\u56fe\u7247\u6587\u4ef6",
    "warn_answer": "\u8bf7\u586b\u5199\u4f5c\u7b54\u6216\u4e0a\u4f20\u4f5c\u7b54\u56fe\u7247",
    "added": "\u5df2\u52a0\u5165\u9519\u9898\u672c",
    "title": "\u4e3e\u4e00\u53cd\u4e09",
    "desc": "\u6839\u636e\u8fd9\u9053\u9519\u9898\u751f\u6210\u540c\u7c7b\u578b\u7ec3\u4e60\uff0c\u9009\u62e9\u96be\u5ea6\u540e\u7b54\u9898\u5e76\u7531 AI \u6279\u6539\u3002",
    "gen_spin": "\u6b63\u5728\u751f\u6210\u9898\u76ee\u2026",
    "pick_diff": "\u9009\u62e9\u96be\u5ea6",
    "regen": "\u91cd\u65b0\u51fa\u9898",
    "gen": "\u751f\u6210\u9898\u76ee",
    "practice": "\u7ec3\u4e60\u9898",
    "your_ans": "\u4f60\u7684\u4f5c\u7b54",
    "text_ans": "\u6587\u5b57\u4f5c\u7b54",
    "ph": "\u5728\u6b64\u8f93\u5165\u4f60\u7684\u7b54\u6848\uff08\u53ef\u4e0e\u56fe\u7247\u4f5c\u7b54\u540c\u65f6\u4f7f\u7528\uff09",
    "upload": "\u4e0a\u4f20\u7eb8\u9762\u4f5c\u7b54\u7167\u7247",
    "rm_img": "\u79fb\u9664\u56fe\u7247",
    "result": "\u6279\u6539\u7ed3\u679c",
    "feedback": "\u8bc4\u8bed",
    "std": "\u6807\u51c6\u7b54\u6848",
    "explain": "\u8bb2\u89e3",
    "again": "\u518d\u7ec3\u4e00\u9898",
    "recheck": "\u91cd\u65b0\u63d0\u4ea4\u6279\u6539",
    "add_nb": "\u6dfb\u52a0\u5230\u9519\u9898\u672c",
    "added_btn": "\u5df2\u52a0\u5165\u9519\u9898\u672c",
    "back": "\u8fd4\u56de\u8be6\u60c5",
    "submit": "\u63d0\u4ea4\u6279\u6539",
    "em": "\u2014",
}

OUT.write_text(
    """<script setup lang="ts">
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
  { value: "easy", label: "%(easy)s" },
  { value: "medium", label: "%(medium)s" },
  { value: "hard", label: "%(hard)s" },
  { value: "challenge", label: "%(challenge)s" },
];

const verdictMeta = computed(() => {
  const v = checkResult.value?.verdict;
  if (v === "correct") return { label: "%(correct)s", type: "success" as const };
  if (v === "partial") return { label: "%(partial)s", type: "warning" as const };
  return { label: "%(wrong)s", type: "error" as const };
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
    message.warning("%(warn_img)s");
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
    message.warning("%(warn_answer)s");
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
    message.success("%(added)s");
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
    <motion.div v-if="row" class="practice page-root" :class="{ 'page-root--fixed-actions': question && !checkResult }">
      <header class="page-header practice__header">
        <h1 class="page-header__title">%(title)s</h1>
        <p class="page-header__desc">%(desc)s</p>
        <NSpace wrap :size="8" class="practice__tags">
          <NTag size="small" type="info">{{ row.subject_name ?? "%(em)s" }}</NTag>
          <NTag size="small">{{ row.grade_name ?? "%(em)s" }}</NTag>
        </NSpace>
      </header>

      <NCard class="surface-card practice__card" size="small" :bordered="false">
        <NSpin :show="generating" description="%(gen_spin)s">
          <NSpace vertical :size="16" style="width: 100%%">
            <section class="practice__section">
              <h2 class="practice__section-title">%(pick_diff)s</h2>
              <motion.div class="practice__difficulty">
                <NRadioGroup v-model:value="difficulty" size="small" :disabled="generating || checking">
                  <NRadioButton v-for="opt in difficultyOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </NRadioButton>
                </NRadioGroup>
                <NButton type="primary" size="small" :loading="generating" :disabled="checking" @click="onGenerate">
                  {{ question ? "%(regen)s" : "%(gen)s" }}
                </NButton>
              </motion.div>
            </section>

            <section v-if="question" class="practice__section">
              <h2 class="practice__section-title">%(practice)s</h2>
              <motion.div class="practice__question">{{ question.question_stem }}</motion.div>
            </section>

            <section v-if="question && !checkResult" class="practice__section">
              <h2 class="practice__section-title">%(your_ans)s</h2>
              <NSpace vertical :size="10" style="width: 100%%">
                <NFormItem label="%(text_ans)s" :show-feedback="false" label-placement="top" class="practice__item">
                  <NInput
                    v-model:value="userAnswer"
                    type="textarea"
                    size="small"
                    placeholder="%(ph)s"
                    :autosize="{ minRows: 3, maxRows: 10 }"
                    :disabled="checking"
                  />
                </NFormItem>
                <motion.div class="practice__upload">
                  <input ref="fileInputRef" type="file" accept="image/*" class="practice__file-input" :disabled="checking" @change="onPickAnswerImage" />
                  <NSpace align="center" wrap :size="8">
                    <NButton size="small" secondary :disabled="checking" @click="fileInputRef?.click()">%(upload)s</NButton>
                    <NButton v-if="answerImage" size="small" quaternary :disabled="checking" @click="resetAnswerImage">%(rm_img)s</NButton>
                  </NSpace>
                  <NImage v-if="answerPreviewUrl" width="100%%" class="practice__answer-image" :src="answerPreviewUrl" object-fit="contain" />
                </motion.div>
              </NSpace>
            </section>

            <section v-if="checkResult" class="practice__section">
              <motion.div class="practice__result-head">
                <h2 class="practice__section-title">%(result)s</h2>
                <NTag size="small" :type="verdictMeta.type">{{ verdictMeta.label }}</NTag>
              </motion.div>
              <motion.div class="practice__result-block">
                <h3 class="practice__result-label">%(feedback)s</h3>
                <motion.div class="practice__result-text"><FormattedAnalysis :text="checkResult.feedback" /></motion.div>
              </motion.div>
              <motion.div class="practice__result-block">
                <h3 class="practice__result-label">%(std)s</h3>
                <motion.div class="practice__result-text">{{ checkResult.standard_answer }}</motion.div>
              </motion.div>
              <motion.div class="practice__result-block">
                <h3 class="practice__result-label">%(explain)s</h3>
                <motion.div class="practice__result-text"><FormattedAnalysis :text="checkResult.explanation" /></motion.div>
              </motion.div>
              <motion.div class="app-actions app-actions--bar practice__result-actions">
                <NButton v-if="showAddToNotebook" size="small" type="primary" :loading="savingToNotebook" @click="addToNotebook">%(add_nb)s</NButton>
                <NButton v-else-if="addedToNotebook" size="small" disabled>%(added_btn)s</NButton>
                <NButton size="small" @click="resetPractice">%(again)s</NButton>
              </motion.div>
            </section>
          </NSpace>
        </NSpin>
      </NCard>

      <Teleport to="body">
        <footer v-if="question && !checkResult" class="app-actions app-actions--bar app-actions--fixed">
          <motion.div class="app-actions--fixed-inner">
            <NButton size="small" @click="backToDetail">%(back)s</NButton>
            <NButton type="primary" size="small" :loading="checking" :disabled="!canSubmit" @click="onCheck">%(submit)s</NButton>
          </motion.div>
        </footer>
      </Teleport>

      <footer v-if="!question || checkResult" class="app-actions app-actions--bar practice__footer">
        <NButton size="small" @click="backToDetail">%(back)s</NButton>
      </footer>
    </motion.div>
  </NSpin>
</template>

<style scoped>
.practice__header { margin-bottom: 12px; }
.practice__tags { margin-top: 8px; }
.practice__card :deep(.n-card__content) { padding: 16px 18px; }
.practice__section-title { margin: 0 0 10px; font-size: 13px; font-weight: 600; color: #334155; }
.practice__difficulty { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.practice__question, .practice__result-text { margin: 0; padding: 12px 14px; border-radius: 10px; border: 1px solid var(--app-border); background: rgba(255, 255, 255, 0.72); font-size: 14px; line-height: 1.65; white-space: pre-wrap; word-break: break-word; color: #0f172a; }
.practice__item { margin-bottom: 0; width: 100%%; }
.practice__item :deep(.n-form-item-label) { padding-bottom: 4px; font-size: 13px; font-weight: 500; }
.practice__item :deep(.n-form-item-blank) { width: 100%%; }
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
"""
    % L,
    encoding="utf-8",
)

text = OUT.read_text(encoding="utf-8")
text = text.replace("<motion.div", "<div").replace("</motion.div>", "</div>")
OUT.write_text(text, encoding="utf-8")
assert "\u4e3e\u4e00\u53cd\u4e09" in text
print("Wrote", OUT)
