<script setup lang="ts">
import { onMounted, ref } from "vue";
import { NButton, NCard, NFormItem, NInputNumber, NSpace, NSpin, NSwitch, useMessage } from "naive-ui";
import { fetchReviewSettings, updateReviewSettings } from "../api/client";

const message = useMessage();
const loading = ref(true);
const saving = ref(false);
const includeMastered = ref(false);
const dailyTarget = ref(10);

async function load() {
  loading.value = true;
  try {
    const s = await fetchReviewSettings();
    includeMastered.value = s.include_mastered_in_review;
    dailyTarget.value = s.daily_review_target;
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}

onMounted(load);

async function save() {
  if (dailyTarget.value == null || dailyTarget.value < 1) {
    message.warning("每日目标至少为 1 题");
    return;
  }
  saving.value = true;
  try {
    await updateReviewSettings({
      include_mastered_in_review: includeMastered.value,
      daily_review_target: dailyTarget.value,
    });
    message.success("已保存");
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <NSpin :show="loading">
    <NSpace vertical :size="16" class="general-settings">
      <p class="general-settings__intro">
        通用设置影响复习计划选题规则，仅对当前登录账号生效。
      </p>
      <NCard class="surface-card" title="复习计划" :segmented="{ content: true }">
        <NSpace vertical :size="16" style="width: 100%">
          <NFormItem label="已掌握题加入复习" :show-feedback="false" label-placement="top" class="general-settings__item">
            <div class="general-settings__switch-row">
              <span class="general-settings__switch-hint">
                关闭时，仅未掌握错题会进入今日待复习；开启后已掌握题也会按间隔再次出现。
              </span>
              <NSwitch v-model:value="includeMastered" :disabled="saving" />
            </div>
          </NFormItem>
          <NFormItem label="每日复习目标（题）" :show-feedback="false" label-placement="top" class="general-settings__item">
            <NInputNumber
              v-model:value="dailyTarget"
              :min="1"
              :max="200"
              clearable
              size="small"
              style="width: 100%; max-width: 200px"
              :disabled="saving"
            />
          </NFormItem>
        </NSpace>
      </NCard>
      <footer class="app-actions app-actions--bar general-settings__actions">
        <NButton type="primary" size="small" :loading="saving" :disabled="loading" @click="save">保存</NButton>
      </footer>
    </NSpace>
  </NSpin>
</template>

<style scoped>
.general-settings__intro {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--app-text-muted, #64748b);
}

.general-settings__item {
  margin-bottom: 0;
  width: 100%;
}

.general-settings__item :deep(.n-form-item-label) {
  padding-bottom: 4px;
  font-size: 13px;
  font-weight: 500;
}

.general-settings__switch-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

.general-settings__switch-hint {
  flex: 1 1 200px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--app-text-muted, #64748b);
}

.general-settings__actions {
  margin-top: 4px;
}

@media (min-width: 769px) {
  .general-settings :deep(.n-card) {
    max-width: 560px;
  }
}
</style>
