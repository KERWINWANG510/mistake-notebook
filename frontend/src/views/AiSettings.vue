<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  NButton,
  NCard,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NSwitch,
  NSpin,
  NTag,
  NText,
  useMessage,
} from "naive-ui";
import type { AiConfig, AiPreset } from "../api/client";
import {
  activateAiConfig,
  createAiConfig,
  deleteAiConfig,
  fetchAiConfigs,
  fetchAiPresets,
  listAiModels,
  listAiModelsPreview,
  updateAiConfig,
} from "../api/client";
import {
  mapVisionModelSelectOptions,
  validateEffectiveVisionSelection,
  visionModelOcrError,
} from "../utils/visionModelCapability";

/** OpenAI 兼容接口常用路径，不在表单中展示，固定使用 */
const DEFAULT_MODELS_PATH = "/models";
const DEFAULT_CHAT_PATH = "/chat/completions";

const message = useMessage();
const loading = ref(true);
const rows = ref<AiConfig[]>([]);
const presets = ref<AiPreset[]>([]);

const showModal = ref(false);
const editingId = ref<string | null>(null);
const userLabel = ref("");
const presetId = ref<string | null>(null);
const baseUrl = ref("");
const apiKey = ref("");
const modelOptions = ref<{ label: string; value: string }[]>([]);
const selectedModel = ref<string | null>(null);
const selectedVision = ref<string | null>(null);
const selectedSolve = ref<string | null>(null);
const listing = ref(false);
const saving = ref(false);

const separateVision = ref(false);
const visionPresetId = ref<string | null>(null);
const visionBaseUrl = ref("");
const visionApiKey = ref("");
const visionModelOptions = ref<{ label: string; value: string }[]>([]);
const listingVision = ref(false);

const separateSolve = ref(false);
const solvePresetId = ref<string | null>(null);
const solveBaseUrl = ref("");
const solveApiKey = ref("");
const solveModelOptions = ref<{ label: string; value: string }[]>([]);
const listingSolve = ref(false);

const visionModelHint = ref("");
const visionModelHintType = ref<"error" | "warning" | "">("");

const visionSelectOptions = computed(() =>
  mapVisionModelSelectOptions(separateVision.value ? visionModelOptions.value : modelOptions.value),
);

function refreshVisionModelHint() {
  const { error, warning, effective } = validateEffectiveVisionSelection(
    selectedVision.value,
    selectedModel.value,
  );
  if (error) {
    visionModelHint.value = error;
    visionModelHintType.value = "error";
    return;
  }
  if (warning) {
    visionModelHint.value = warning;
    visionModelHintType.value = "warning";
    return;
  }
  if (!selectedVision.value?.trim() && effective) {
    visionModelHint.value = `未单独指定识图模型时，将使用默认模型「${effective}」进行 OCR`;
    visionModelHintType.value = "";
    return;
  }
  visionModelHint.value = "";
  visionModelHintType.value = "";
}

function onVisionModelChange(v: string | null) {
  const id = (v ?? "").trim();
  if (id) {
    const err = visionModelOcrError(id);
    if (err) {
      message.error(err);
      selectedVision.value = null;
      refreshVisionModelHint();
      return;
    }
  }
  selectedVision.value = v;
  refreshVisionModelHint();
}

watch([selectedVision, selectedModel], refreshVisionModelHint);

const canFetchModels = computed(() => {
  const hasUrl = Boolean(baseUrl.value.trim());
  const hasKeyOrSaved = Boolean(apiKey.value.trim()) || Boolean(editingId.value);
  return hasUrl && hasKeyOrSaved;
});

const canFetchVisionModels = computed(() => {
  if (!separateVision.value) return false;
  const hasUrl = Boolean(visionBaseUrl.value.trim());
  const hasKeyOrSaved = Boolean(visionApiKey.value.trim()) || Boolean(editingId.value);
  return hasUrl && hasKeyOrSaved;
});

const canFetchSolveModels = computed(() => {
  if (!separateSolve.value) return false;
  const hasUrl = Boolean(solveBaseUrl.value.trim());
  const hasKeyOrSaved = Boolean(solveApiKey.value.trim()) || Boolean(editingId.value);
  return hasUrl && hasKeyOrSaved;
});

const presetOptions = computed(() => presets.value.map((p) => ({ label: p.display_name, value: p.id })));

function applyPreset(id: string | null) {
  const p = presets.value.find((x) => x.id === id);
  if (!p) return;
  if (p.default_base_url) baseUrl.value = p.default_base_url;
}

function applyVisionPreset(id: string | null) {
  const p = presets.value.find((x) => x.id === id);
  if (!p) return;
  if (p.default_base_url) visionBaseUrl.value = p.default_base_url;
}

function applySolvePreset(id: string | null) {
  const p = presets.value.find((x) => x.id === id);
  if (!p) return;
  if (p.default_base_url) solveBaseUrl.value = p.default_base_url;
}

function onSeparateVision(v: boolean) {
  separateVision.value = v;
  if (!v) {
    visionPresetId.value = null;
    visionBaseUrl.value = "";
    visionApiKey.value = "";
    visionModelOptions.value = [];
    selectedVision.value = null;
  }
}

function onSeparateSolve(v: boolean) {
  separateSolve.value = v;
  if (!v) {
    solvePresetId.value = null;
    solveBaseUrl.value = "";
    solveApiKey.value = "";
    solveModelOptions.value = [];
  }
}

async function load() {
  loading.value = true;
  try {
    const [cs, ps] = await Promise.all([fetchAiConfigs(), fetchAiPresets()]);
    rows.value = cs;
    presets.value = ps;
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}

onMounted(load);

function resetModalForm() {
  separateVision.value = false;
  visionPresetId.value = null;
  visionBaseUrl.value = "";
  visionApiKey.value = "";
  visionModelOptions.value = [];
  separateSolve.value = false;
  solvePresetId.value = null;
  solveBaseUrl.value = "";
  solveApiKey.value = "";
  solveModelOptions.value = [];
}

function openCreate() {
  editingId.value = null;
  userLabel.value = "";
  presetId.value = presets.value[0]?.id ?? null;
  apiKey.value = "";
  modelOptions.value = [];
  selectedModel.value = null;
  selectedVision.value = null;
  selectedSolve.value = null;
  resetModalForm();
  applyPreset(presetId.value);
  if (!baseUrl.value && presetId.value === "custom_openai") {
    baseUrl.value = "";
  }
  visionModelHint.value = "";
  visionModelHintType.value = "";
  showModal.value = true;
}

function onPresetChange(v: string | null) {
  presetId.value = v;
  applyPreset(v);
}

async function saveDraft() {
  if (!userLabel.value.trim()) {
    message.warning("请填写配置名称");
    return;
  }
  if (!baseUrl.value.trim()) {
    message.warning("请填写主接入的 Base URL");
    return;
  }
  if (separateVision.value) {
    if (!visionBaseUrl.value.trim()) {
      message.warning("已开启「识图独立服务商」，请填写识图侧的 Base URL");
      return;
    }
    if (!editingId.value && !visionApiKey.value.trim()) {
      message.warning("已开启「识图独立服务商」，请填写识图侧的 API Key");
      return;
    }
  }
  if (separateSolve.value) {
    if (!solveBaseUrl.value.trim()) {
      message.warning("已开启「解题独立服务商」，请填写解题侧的 Base URL");
      return;
    }
    if (!editingId.value && !solveApiKey.value.trim()) {
      message.warning("已开启「解题独立服务商」，请填写解题侧的 API Key");
      return;
    }
  }

  const visionCheck = validateEffectiveVisionSelection(
    selectedVision.value,
    selectedModel.value,
  );
  if (!visionCheck.ok) {
    message.error(visionCheck.error ?? "所选模型不支持 OCR 识图");
    return;
  }
  if (visionCheck.warning) {
    message.warning(visionCheck.warning);
  }

  saving.value = true;
  try {
    if (editingId.value) {
      const payload: Record<string, unknown> = {
        user_label: userLabel.value.trim(),
        base_url: baseUrl.value.trim(),
        models_path: DEFAULT_MODELS_PATH,
        chat_path: DEFAULT_CHAT_PATH,
        selected_model: selectedModel.value,
        selected_model_vision: selectedVision.value,
        selected_model_solve: selectedSolve.value,
      };
      if (apiKey.value.trim()) payload.api_key = apiKey.value.trim();

      if (!separateVision.value) {
        payload.vision_base_url = null;
        payload.vision_preset_id = null;
        payload.vision_api_key = null;
      } else {
        payload.vision_base_url = visionBaseUrl.value.trim();
        payload.vision_preset_id = visionPresetId.value;
        if (visionApiKey.value.trim()) payload.vision_api_key = visionApiKey.value.trim();
      }
      if (!separateSolve.value) {
        payload.solve_base_url = null;
        payload.solve_preset_id = null;
        payload.solve_api_key = null;
      } else {
        payload.solve_base_url = solveBaseUrl.value.trim();
        payload.solve_preset_id = solvePresetId.value;
        if (solveApiKey.value.trim()) payload.solve_api_key = solveApiKey.value.trim();
      }

      await updateAiConfig(editingId.value, payload as Parameters<typeof updateAiConfig>[1]);
      message.success("已保存");
    } else {
      const c = await createAiConfig({
        user_label: userLabel.value.trim(),
        preset_id: presetId.value,
        base_url: baseUrl.value.trim(),
        models_path: DEFAULT_MODELS_PATH,
        chat_path: DEFAULT_CHAT_PATH,
        api_key: apiKey.value || null,
        selected_model: selectedModel.value,
        selected_model_vision: selectedVision.value,
        selected_model_solve: selectedSolve.value,
        vision_preset_id: separateVision.value ? visionPresetId.value : null,
        vision_base_url: separateVision.value ? visionBaseUrl.value.trim() || null : null,
        vision_api_key: separateVision.value ? visionApiKey.value.trim() || null : null,
        solve_preset_id: separateSolve.value ? solvePresetId.value : null,
        solve_base_url: separateSolve.value ? solveBaseUrl.value.trim() || null : null,
        solve_api_key: separateSolve.value ? solveApiKey.value.trim() || null : null,
      });
      editingId.value = c.id;
      message.success("已保存");
    }
    showModal.value = false;
    await load();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    saving.value = false;
  }
}

async function fetchModels() {
  const bu = baseUrl.value.trim();
  if (!bu) {
    message.warning("请先填写 API 根地址（Base URL）");
    return;
  }
  const mp = DEFAULT_MODELS_PATH;
  const keyTrim = apiKey.value.trim();

  listing.value = true;
  try {
    const res = keyTrim
      ? await listAiModelsPreview({ base_url: bu, models_path: mp, api_key: keyTrim })
      : editingId.value
        ? await listAiModels(editingId.value, "main")
        : null;
    if (res === null) {
      message.warning("请填写 API Key，或先保存一次配置后再拉取（已保存的密钥可留空拉取）");
      return;
    }
    if (!res.ok) {
      message.error(res.message ?? res.error_code ?? "拉取失败");
      return;
    }
    modelOptions.value = res.models.map((m) => ({ label: m.id, value: m.id }));
    refreshVisionModelHint();
    message.success(`主接入：获取到 ${modelOptions.value.length} 个模型`);
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    listing.value = false;
  }
}

async function fetchVisionModels() {
  const bu = visionBaseUrl.value.trim();
  if (!bu) {
    message.warning("请先填写识图侧的 Base URL");
    return;
  }
  const mp = DEFAULT_MODELS_PATH;
  const keyTrim = visionApiKey.value.trim();

  listingVision.value = true;
  try {
    const res = keyTrim
      ? await listAiModelsPreview({ base_url: bu, models_path: mp, api_key: keyTrim })
      : editingId.value
        ? await listAiModels(editingId.value, "vision")
        : null;
    if (res === null) {
      message.warning("请填写识图侧 API Key，或先保存配置后再拉取");
      return;
    }
    if (!res.ok) {
      message.error(res.message ?? res.error_code ?? "拉取失败");
      return;
    }
    visionModelOptions.value = res.models.map((m) => ({ label: m.id, value: m.id }));
    refreshVisionModelHint();
    message.success(`识图接入：获取到 ${visionModelOptions.value.length} 个模型`);
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    listingVision.value = false;
  }
}

async function fetchSolveModels() {
  const bu = solveBaseUrl.value.trim();
  if (!bu) {
    message.warning("请先填写解题侧的 Base URL");
    return;
  }
  const mp = DEFAULT_MODELS_PATH;
  const keyTrim = solveApiKey.value.trim();

  listingSolve.value = true;
  try {
    const res = keyTrim
      ? await listAiModelsPreview({ base_url: bu, models_path: mp, api_key: keyTrim })
      : editingId.value
        ? await listAiModels(editingId.value, "solve")
        : null;
    if (res === null) {
      message.warning("请填写解题侧 API Key，或先保存配置后再拉取");
      return;
    }
    if (!res.ok) {
      message.error(res.message ?? res.error_code ?? "拉取失败");
      return;
    }
    solveModelOptions.value = res.models.map((m) => ({ label: m.id, value: m.id }));
    message.success(`解题接入：获取到 ${solveModelOptions.value.length} 个模型`);
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    listingSolve.value = false;
  }
}

async function activate(id: string) {
  try {
    await activateAiConfig(id);
    message.success("已切换为当前配置");
    await load();
  } catch (e) {
    message.error((e as Error).message);
  }
}

async function remove(id: string) {
  try {
    await deleteAiConfig(id);
    message.success("已删除");
    await load();
  } catch (e) {
    message.error((e as Error).message);
  }
}


function bindEditForm(r: AiConfig) {
  editingId.value = r.id;
  userLabel.value = r.user_label;
  presetId.value = r.preset_id;
  baseUrl.value = r.base_url;
  apiKey.value = "";
  selectedModel.value = r.selected_model;
  selectedSolve.value = r.selected_model_solve ?? null;

  resetModalForm();

  const hasSeparateVision = Boolean(r.vision_base_url?.trim());
  separateVision.value = hasSeparateVision;
  if (hasSeparateVision) {
    visionPresetId.value = r.vision_preset_id ?? null;
    visionBaseUrl.value = r.vision_base_url ?? "";
    visionApiKey.value = "";
    selectedVision.value = r.selected_model_vision ?? null;
  } else {
    selectedVision.value = r.selected_model_vision ?? null;
  }

  const hasSeparateSolve = Boolean(r.solve_base_url?.trim());
  separateSolve.value = hasSeparateSolve;
  if (hasSeparateSolve) {
    solvePresetId.value = r.solve_preset_id ?? null;
    solveBaseUrl.value = r.solve_base_url ?? "";
    solveApiKey.value = "";
  }

  const ids = new Set<string>();
  for (const x of [r.selected_model, r.selected_model_vision, r.selected_model_solve]) {
    if (x) ids.add(x);
  }
  modelOptions.value = [...ids].map((id) => ({ label: id, value: id }));
  if (hasSeparateVision && r.selected_model_vision) {
    visionModelOptions.value = [{ label: r.selected_model_vision, value: r.selected_model_vision }];
  }
  if (hasSeparateSolve && r.selected_model_solve) {
    solveModelOptions.value = [{ label: r.selected_model_solve, value: r.selected_model_solve }];
  }
}

async function openEdit(r: AiConfig) {
  try {
    await load();
  } catch (e) {
    message.error((e as Error).message);
    return;
  }
  const fresh = rows.value.find((x) => x.id === r.id);
  if (!fresh) {
    message.warning("配置不存在或已删除");
    return;
  }
  bindEditForm(fresh);
  refreshVisionModelHint();
  showModal.value = true;
}
</script>

<template>
  <NSpace vertical :size="16" class="ai-settings">
    <p class="ai-settings__intro">
      以下配置仅对当前登录账号生效，与其他用户互不可见。主接入用于默认识图与解题；若识图或解题需走另一家厂商，可分别开启独立服务商并填写对应地址与密钥。
    </p>
    <NCard class="surface-card" title="配置列表" :segmented="{ content: true }">
      <NSpace vertical :size="12" style="width: 100%">
        <NButton type="primary" @click="openCreate">新建配置</NButton>
        <NSpin :show="loading">
          <div class="entity-card-list entity-card-list--auto-grid ai-settings__list">
            <NCard v-for="r in rows" :key="r.id" class="entity-card ai-settings__card mistake-row-card" size="small" embedded>
              <div class="entity-card__head">
                <span class="entity-card__title">{{ r.user_label }}</span>
                <NTag v-if="r.is_active" type="success" size="small">当前</NTag>
              </div>
              <div class="entity-card__rows">
                <div class="entity-card__row">
                  <span class="entity-card__label">地址</span>
                  <span class="entity-card__value">{{ r.base_url }}</span>
                </div>
                <div class="entity-card__row">
                  <span class="entity-card__label">默认模型</span>
                  <span class="entity-card__value">{{ r.selected_model ?? "—" }}</span>
                </div>
                <div class="entity-card__row">
                  <span class="entity-card__label">识图</span>
                  <span class="entity-card__value entity-card__value--inline">
                    {{ r.selected_model_vision ?? "（同默认）" }}
                    <NTag v-if="r.vision_base_url?.trim()" size="small" type="info" :bordered="false">独立</NTag>
                  </span>
                </div>
                <div class="entity-card__row">
                  <span class="entity-card__label">解题</span>
                  <span class="entity-card__value entity-card__value--inline">
                    {{ r.selected_model_solve ?? "（同默认）" }}
                    <NTag v-if="r.solve_base_url?.trim()" size="small" type="info" :bordered="false">独立</NTag>
                  </span>
                </div>
                <div class="entity-card__row">
                  <span class="entity-card__label">密钥</span>
                  <span class="entity-card__value">{{ r.has_api_key ? "已配置" : "未配置" }}</span>
                </div>
              </div>
              <div class="entity-card__actions">
                <NButton size="small" type="primary" secondary :disabled="r.is_active" @click="activate(r.id)">
                  设为当前
                </NButton>
                <NButton size="small" tertiary @click="openEdit(r)">编辑</NButton>
                <NButton size="small" type="error" secondary :disabled="r.is_active" @click="remove(r.id)">删除</NButton>
              </div>
            </NCard>
            <div v-if="!loading && rows.length === 0" class="entity-card__empty">暂无 AI 配置</div>
          </div>
        </NSpin>
      </NSpace>
    </NCard>

    <NModal v-model:show="showModal" style="width: min(640px, 92vw)" preset="dialog" :title="editingId ? '编辑配置' : '新建配置'">
      <NSpace vertical style="width: 100%; margin-top: 12px" :size="12">
        <NInput v-model:value="userLabel" placeholder="便于识别的配置名称，如「家用 OpenAI」" />
        <NSelect v-model:value="presetId" :options="presetOptions" placeholder="选择服务商或接口预设" @update:value="onPresetChange" />
        <NText depth="3" style="font-size: 13px">主接入（默认）</NText>
        <NInput v-model:value="baseUrl" placeholder="API 根地址（Base URL），通常已由预设自动填写" />
        <div class="app-field-row">
          <NInput
            v-model:value="apiKey"
            type="password"
            show-password-on="click"
            placeholder="主接入 API Key；编辑时留空表示不修改"
            class="app-field-row__grow"
          />
          <NButton :disabled="!canFetchModels" :loading="listing" @click="fetchModels">拉取模型列表</NButton>
        </div>
        <NSelect
          v-model:value="selectedModel"
          filterable
          tag
          placeholder="默认模型：识图与解题未单独指定时使用"
          :options="modelOptions"
          style="width: 100%"
        />

        <NSpace align="center" justify="space-between" style="width: 100%">
          <NText strong>识图使用独立服务商</NText>
          <NSwitch :value="separateVision" @update:value="onSeparateVision" />
        </NSpace>
        <template v-if="separateVision">
          <NSelect
            v-model:value="visionPresetId"
            :options="presetOptions"
            placeholder="识图侧厂商预设（可选）"
            clearable
            @update:value="applyVisionPreset"
          />
          <NInput v-model:value="visionBaseUrl" placeholder="识图侧 Base URL" />
          <div class="app-field-row">
            <NInput
              v-model:value="visionApiKey"
              type="password"
              show-password-on="click"
              placeholder="识图侧 API Key；编辑已保存配置时留空表示沿用已存密钥"
              class="app-field-row__grow"
            />
            <NButton :disabled="!canFetchVisionModels" :loading="listingVision" @click="fetchVisionModels">
              拉取识图模型
            </NButton>
          </div>
        </template>
        <NSelect
          :value="selectedVision"
          filterable
          tag
          clearable
          :placeholder="
            separateVision
              ? '识图模型（在识图独立服务商下选择，需先拉取列表）'
              : '识图 / OCR 模型（可留空，留空则与默认模型相同）'
          "
          :options="visionSelectOptions"
          style="width: 100%"
          @update:value="onVisionModelChange"
        />
        <NText
          v-if="visionModelHint"
          :type="visionModelHintType === 'error' ? 'error' : visionModelHintType === 'warning' ? 'warning' : undefined"
          depth="3"
          style="font-size: 12px; display: block; margin-top: -4px"
        >
          {{ visionModelHint }}
        </NText>

        <NSpace align="center" justify="space-between" style="width: 100%">
          <NText strong>解题使用独立服务商</NText>
          <NSwitch :value="separateSolve" @update:value="onSeparateSolve" />
        </NSpace>
        <template v-if="separateSolve">
          <NSelect
            v-model:value="solvePresetId"
            :options="presetOptions"
            placeholder="解题侧厂商预设（可选）"
            clearable
            @update:value="applySolvePreset"
          />
          <NInput v-model:value="solveBaseUrl" placeholder="解题侧 Base URL" />
          <div class="app-field-row">
            <NInput
              v-model:value="solveApiKey"
              type="password"
              show-password-on="click"
              placeholder="解题侧 API Key；编辑已保存配置时留空表示沿用已存密钥"
              class="app-field-row__grow"
            />
            <NButton :disabled="!canFetchSolveModels" :loading="listingSolve" @click="fetchSolveModels">
              拉取解题模型
            </NButton>
          </div>
        </template>
        <NSelect
          v-model:value="selectedSolve"
          filterable
          tag
          clearable
          :placeholder="
            separateSolve
              ? '解题模型（在解题独立服务商下选择，需先拉取列表）'
              : '解题与科目推断模型（可留空，留空则与默认模型相同）'
          "
          :options="separateSolve ? solveModelOptions : modelOptions"
          style="width: 100%"
        />

        <div class="app-actions">
          <NButton @click="showModal = false">关闭</NButton>
          <NButton type="primary" :loading="saving" @click="saveDraft">保存</NButton>
        </div>
      </NSpace>
    </NModal>
  </NSpace>
</template>

<style scoped>
.ai-settings__intro {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--app-text-muted, #64748b);
}

/* 配置卡片：更紧凑，按宽度自动多列换行 */
.ai-settings__list.entity-card-list--auto-grid {
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 220px), 1fr));
  gap: 10px;
}

.ai-settings__list :deep(.ai-settings__card .n-card__content) {
  padding: 10px 12px;
}

.ai-settings__list :deep(.entity-card__head) {
  margin-bottom: 6px;
}

.ai-settings__list :deep(.entity-card__title) {
  font-size: 14px;
  line-height: 1.35;
}

.ai-settings__list :deep(.entity-card__rows) {
  gap: 4px;
}

.ai-settings__list :deep(.entity-card__row) {
  font-size: 12px;
  gap: 8px;
}

.ai-settings__list :deep(.entity-card__label) {
  flex: 0 0 3.5em;
}

.ai-settings__list :deep(.entity-card__value) {
  font-size: 12px;
  line-height: 1.45;
}

.ai-settings__list :deep(.entity-card__actions) {
  margin-top: 8px;
  padding-top: 8px;
  gap: 6px;
}

@media (min-width: 900px) {
  .ai-settings__list.entity-card-list--auto-grid {
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  }
}
</style>
