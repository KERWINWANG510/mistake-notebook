<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NDynamicTags, NFormItem, NImage, NInput, NSelect, NSpace, NSwitch, NSpin, useMessage } from "naive-ui";
import AnalysisField from "../components/AnalysisField.vue";
import { ERROR_REASON_OPTIONS } from "../constants/errorReasons";
import { MISTAKE_SOURCE_OPTIONS } from "../constants/mistakeSources";
import type { Grade, Mistake, Subject } from "../api/client";
import {
  fetchGrades,
  fetchMistake,
  fetchMistakeImageObjectUrl,
  fetchSubjects,
  replaceMistakeImage,
  solveFromStem,
  updateMistake,
} from "../api/client";
import { parseAppReturnTo } from "../utils/returnNavigation";

const route = useRoute();
const router = useRouter();
const message = useMessage();

const id = computed(() => route.params.id as string);
const loading = ref(true);
const saving = ref(false);
const uploading = ref(false);
const solvingStem = ref(false);
const row = ref<Mistake | null>(null);
const subjects = ref<Subject[]>([]);
const grades = ref<Grade[]>([]);

const stem = ref("");
const analysis = ref("");
const answer = ref("");
const subjectId = ref<string | null>(null);
const gradeLevelId = ref<string | null>(null);
const isMastered = ref(false);
const knowledgeTags = ref<string[]>([]);
const errorReason = ref<string | null>(null);
const mistakeSource = ref<string | null>(null);

const errorReasonOptions = ERROR_REASON_OPTIONS.map((o) => ({ label: o.label, value: o.value }));
const mistakeSourceOptions = MISTAKE_SOURCE_OPTIONS.map((o) => ({ label: o.label, value: o.value }));

const imageObjectUrl = ref<string | null>(null);
const imageInputRef = ref<HTMLInputElement | null>(null);

const subjectOptions = computed(() => subjects.value.map((s) => ({ label: s.name, value: s.id })));
const gradeOptions = computed(() => grades.value.map((g) => ({ label: g.name, value: g.id })));

/** 保存/取消后返回：优先回到进入编辑页时的路径 */
function pathAfterEdit(): string {
  return parseAppReturnTo(route.query as Record<string, unknown>) ?? `/mistakes/${id.value}`;
}

function leaveEditPage() {
  router.push(pathAfterEdit());
}

async function loadSubjectsForGrade(gradeId: string | null) {
  if (!gradeId) {
    subjects.value = [];
    return;
  }
  try {
    subjects.value = await fetchSubjects({ grade_level_id: gradeId });
    if (subjectId.value && !subjects.value.some((s) => s.id === subjectId.value)) {
      subjectId.value = subjects.value[0]?.id ?? null;
    }
  } catch (e) {
    message.error((e as Error).message);
    subjects.value = [];
  }
}

async function loadImageBlob() {
  if (imageObjectUrl.value) {
    URL.revokeObjectURL(imageObjectUrl.value);
    imageObjectUrl.value = null;
  }
  if (!row.value?.image_path) return;
  try {
    imageObjectUrl.value = await fetchMistakeImageObjectUrl(id.value);
  } catch {
    imageObjectUrl.value = null;
  }
}

async function load() {
  loading.value = true;
  try {
    const [m, gs] = await Promise.all([fetchMistake(id.value), fetchGrades()]);
    row.value = m;
    stem.value = m.stem;
    analysis.value = m.analysis;
    answer.value = m.answer;
    subjectId.value = m.subject_id;
    gradeLevelId.value = m.grade_level_id;
    isMastered.value = m.is_mastered;
    knowledgeTags.value = [...(m.knowledge_tags ?? [])];
    errorReason.value = m.error_reason ?? null;
    mistakeSource.value = m.mistake_source ?? null;
    grades.value = gs;
    await loadSubjectsForGrade(m.grade_level_id);
    await loadImageBlob();
  } catch (e) {
    message.error((e as Error).message);
    router.push("/mistakes");
  } finally {
    loading.value = false;
  }
}

onMounted(load);

onBeforeUnmount(() => {
  if (imageObjectUrl.value) URL.revokeObjectURL(imageObjectUrl.value);
});

/** 从拖拽数据中取第一张图片文件 */
function pickFirstImageFile(dt: DataTransfer | null): File | null {
  if (!dt) return null;
  const list = dt.files;
  if (list?.length) {
    for (let i = 0; i < list.length; i++) {
      const file = list[i];
      if (file.type.startsWith("image/")) return file;
    }
  }
  const items = dt.items;
  if (items?.length) {
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      if (it.kind === "file") {
        const file = it.getAsFile();
        if (file?.type.startsWith("image/")) return file;
      }
    }
  }
  return null;
}

const imageDropActive = ref(false);

function onReplaceImageDragOver(e: DragEvent) {
  e.preventDefault();
  if (e.dataTransfer) {
    e.dataTransfer.dropEffect = uploading.value || solvingStem.value ? "none" : "copy";
  }
}

function onReplaceImageDragEnter(e: DragEvent) {
  if (uploading.value || solvingStem.value) return;
  e.preventDefault();
  imageDropActive.value = true;
}

function onReplaceImageDragLeave(e: DragEvent) {
  const root = e.currentTarget as HTMLElement;
  const rel = e.relatedTarget as Node | null;
  if (rel && root.contains(rel)) return;
  imageDropActive.value = false;
}

async function onReplaceImageDrop(e: DragEvent) {
  e.preventDefault();
  imageDropActive.value = false;
  if (uploading.value || solvingStem.value) {
    message.warning("请等待当前操作完成后再上传图片");
    return;
  }
  const f = pickFirstImageFile(e.dataTransfer);
  if (!f) {
    message.warning("请拖拽图片文件（如 JPG、PNG）到此处");
    return;
  }
  await applyReplaceImageFile(f);
}

async function applyReplaceImageFile(f: File) {
  if (!f.type.startsWith("image/")) {
    message.warning("请上传图片文件（如 JPG、PNG、WebP）");
    return;
  }
  uploading.value = true;
  try {
    await replaceMistakeImage(id.value, f);
    message.success("图片已更新");
    await load();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    uploading.value = false;
  }
}

async function onReplaceImage(e: Event) {
  const input = e.target as HTMLInputElement;
  const f = input.files?.[0];
  input.value = "";
  if (!f) return;
  await applyReplaceImageFile(f);
}

function triggerReplaceImage() {
  if (uploading.value) return;
  imageInputRef.value?.click();
}

async function runSolveFromStem() {
  const text = stem.value.trim();
  if (!text) {
    message.warning("请先填写题干");
    return;
  }
  solvingStem.value = true;
  try {
    const subj = subjects.value.find((s) => s.id === subjectId.value);
    const grade = grades.value.find((g) => g.id === gradeLevelId.value);
    const res = await solveFromStem(text, {
      subject_code: subj?.code ?? null,
      grade_level: grade?.level ?? null,
    });
    analysis.value = res.analysis;
    answer.value = res.answer;
    const matched = subjects.value.find((s) => s.code === res.suggested_subject_code);
    if (matched) subjectId.value = matched.id;
    if (res.suggested_grade_level != null) {
      const g = grades.value.find((x) => x.level === res.suggested_grade_level);
      if (g) {
        gradeLevelId.value = g.id;
        await loadSubjectsForGrade(g.id);
      }
    }
    if (res.knowledge_tags?.length) {
      knowledgeTags.value = [...res.knowledge_tags];
    }
    message.success("已根据题干重新生成解析、答案与知识点标签");
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    solvingStem.value = false;
  }
}

async function save() {
  if (!subjectId.value || !gradeLevelId.value) {
    message.warning("请选择科目与年级");
    return;
  }
  if (!stem.value.trim()) {
    message.warning("题干不能为空");
    return;
  }
  if (!errorReason.value) {
    message.warning("请选择错因");
    return;
  }
  if (!mistakeSource.value) {
    message.warning("请选择错题来源");
    return;
  }
  saving.value = true;
  try {
    await updateMistake(id.value, {
      subject_id: subjectId.value,
      grade_level_id: gradeLevelId.value,
      stem: stem.value,
      analysis: analysis.value,
      answer: answer.value,
      is_mastered: isMastered.value,
      knowledge_tags: knowledgeTags.value,
      error_reason: errorReason.value,
      mistake_source: mistakeSource.value,
    });
    message.success("已保存");
    leaveEditPage();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <NSpin :show="loading">
    <div v-if="row" class="mistake-edit page-root page-root--fixed-actions">
      <header class="page-header mistake-edit__header">
        <h1 class="page-header__title">编辑错题</h1>
        <p class="page-header__desc">修改分类、题干或解答内容；保存后返回详情页查看。</p>
      </header>

      <NCard class="surface-card mistake-edit__card" size="small" :bordered="false">
        <NSpin :show="solvingStem" description="正在根据题干生成解析…">
          <input
            ref="imageInputRef"
            type="file"
            accept="image/*"
            class="hidden-file-input"
            :disabled="uploading"
            @change="onReplaceImage"
          />
          <NSpace vertical :size="14" style="width: 100%">
            <section v-if="row.image_path || imageObjectUrl" class="mistake-edit__section">
              <h2 class="mistake-edit__section-title">题目图片</h2>
              <p class="mistake-edit__image-hint">支持点击「编辑配图」或将图片拖入下方预览区域更换。</p>
              <div
                class="mistake-edit__image-wrap"
                :class="{ 'mistake-edit__image-wrap--dragover': imageDropActive }"
                @dragenter.prevent="onReplaceImageDragEnter"
                @dragover.prevent="onReplaceImageDragOver"
                @dragleave.prevent="onReplaceImageDragLeave"
                @drop.prevent="onReplaceImageDrop"
              >
                <NImage
                  v-if="imageObjectUrl"
                  width="100%"
                  class="mistake-edit__image"
                  :src="imageObjectUrl"
                  object-fit="contain"
                />
                <div v-else class="mistake-edit__image-placeholder">配图加载失败，可点击右上角重新上传</div>
                <NButton
                  class="mistake-edit__image-edit"
                  size="tiny"
                  secondary
                  :loading="uploading"
                  @click="triggerReplaceImage"
                >
                  编辑配图
                </NButton>
              </div>
            </section>

            <div class="mistake-edit__meta">
              <NFormItem label="年级" :show-feedback="false" class="mistake-edit__item mistake-edit__item--inline" label-placement="top">
                <NSelect
                  v-model:value="gradeLevelId"
                  size="small"
                  class="mistake-edit__select"
                  placeholder="请选择年级"
                  :options="gradeOptions"
                  @update:value="(v) => void loadSubjectsForGrade(v)"
                />
              </NFormItem>
              <NFormItem label="科目" :show-feedback="false" class="mistake-edit__item mistake-edit__item--inline" label-placement="top">
                <NSelect
                  v-model:value="subjectId"
                  size="small"
                  class="mistake-edit__select"
                  placeholder="请选择科目"
                  :options="subjectOptions"
                  :disabled="!gradeLevelId"
                />
              </NFormItem>
            </div>

            <NFormItem label="错因" :show-feedback="false" class="mistake-edit__item" label-placement="top">
              <NSelect
                v-model:value="errorReason"
                size="small"
                class="mistake-edit__select"
                placeholder="请选择错因"
                :options="errorReasonOptions"
                clearable
              />
            </NFormItem>

            <NFormItem label="错题来源" :show-feedback="false" class="mistake-edit__item" label-placement="top">
              <NSelect
                v-model:value="mistakeSource"
                size="small"
                class="mistake-edit__select"
                placeholder="请选择来源"
                :options="mistakeSourceOptions"
                clearable
              />
            </NFormItem>

            <NFormItem label="掌握状态" :show-feedback="false" class="mistake-edit__item" label-placement="top">
              <NSwitch v-model:value="isMastered">
                <template #checked>已掌握</template>
                <template #unchecked>未掌握</template>
              </NSwitch>
            </NFormItem>

            <NFormItem label="知识点标签" :show-feedback="false" class="mistake-edit__item" label-placement="top">
              <NDynamicTags v-model:value="knowledgeTags" size="small" :max="6" placeholder="回车添加标签" />
            </NFormItem>

            <NFormItem label="题干" :show-feedback="false" class="mistake-edit__item" label-placement="top">
              <NSpace vertical :size="8" style="width: 100%">
                <AnalysisField
                  v-model="stem"
                  variant="stem"
                  :min-rows="4"
                  :max-rows="14"
                  empty-text="请填写题干"
                />
                <NButton
                  size="small"
                  secondary
                  :loading="solvingStem"
                  :disabled="!stem.trim()"
                  @click="runSolveFromStem"
                >
                  根据题干重新生成解析与答案
                </NButton>
              </NSpace>
            </NFormItem>

            <NFormItem label="解题思路" :show-feedback="false" class="mistake-edit__item" label-placement="top">
              <AnalysisField
                v-model="analysis"
                empty-text="暂无解题思路，可根据题干重新生成"
              />
            </NFormItem>

            <NFormItem label="答案" :show-feedback="false" class="mistake-edit__item" label-placement="top">
              <NInput
                v-model:value="answer"
                type="textarea"
                size="small"
                placeholder="最终答案"
                :autosize="{ minRows: 2, maxRows: 10 }"
              />
            </NFormItem>
          </NSpace>
        </NSpin>
      </NCard>

      <Teleport to="body">
        <footer class="app-actions app-actions--bar app-actions--fixed">
          <div class="app-actions--fixed-inner">
            <NButton size="small" @click="leaveEditPage">取消</NButton>
            <NButton type="primary" size="small" :loading="saving" :disabled="solvingStem" @click="save">
              保存修改
            </NButton>
          </div>
        </footer>
      </Teleport>
    </div>
  </NSpin>
</template>

<style scoped>
.mistake-edit__header {
  margin-bottom: 12px;
}

.mistake-edit__card :deep(.n-card__content) {
  padding: 16px 18px;
}

.mistake-edit__section-title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.mistake-edit__image-wrap {
  position: relative;
  display: inline-block;
  width: 100%;
  max-width: 520px;
}

.mistake-edit__image-wrap--dragover {
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.55);
  border-radius: 12px;
}

.mistake-edit__image-hint {
  margin: 0 0 8px;
  font-size: 12px;
  line-height: 1.45;
  color: var(--app-text-subtle, #64748b);
}

.mistake-edit__image {
  display: block;
  width: 100%;
  border-radius: 12px;
}

.mistake-edit__image-placeholder {
  min-height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  border-radius: 12px;
  border: 1px dashed var(--app-border);
  background: rgba(255, 255, 255, 0.65);
  font-size: 13px;
  color: var(--app-text-muted);
  text-align: center;
  line-height: 1.5;
}

.mistake-edit__image-edit {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 2;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.12);
}

.hidden-file-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

.mistake-edit__item {
  margin-bottom: 0;
}

.mistake-edit__item :deep(.n-form-item-label) {
  padding-bottom: 4px;
  font-size: 13px;
  font-weight: 500;
}

.mistake-edit__item--inline {
  flex: 1;
  min-width: 0;
}

.mistake-edit__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  width: 100%;
}

.mistake-edit__select {
  width: 100%;
  min-width: 0;
}

@media (max-width: 768px) {
  .mistake-edit__meta {
    flex-direction: column;
  }

  .mistake-edit__item--inline {
    width: 100%;
  }
}
</style>
