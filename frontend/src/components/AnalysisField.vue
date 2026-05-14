<script setup lang="ts">
import { ref } from "vue";
import { NButton, NInput, NSpace } from "naive-ui";
import FormattedAnalysis from "./FormattedAnalysis.vue";

defineProps<{
  emptyText?: string;
  minRows?: number;
  maxRows?: number;
  placeholder?: string;
  /** 与 FormattedAnalysis 一致；题干请传 stem */
  variant?: "analysis" | "stem";
}>();

const model = defineModel<string>({ default: "" });

const mode = ref<"edit" | "preview">("preview");
</script>

<template>
  <div class="analysis-field">
    <div class="analysis-field__toolbar">
      <NSpace :size="6" align="center">
        <NButton
          size="tiny"
          :type="mode === 'edit' ? 'primary' : 'default'"
          :secondary="mode !== 'edit'"
          @click="mode = 'edit'"
        >
          编辑
        </NButton>
        <NButton
          size="tiny"
          :type="mode === 'preview' ? 'primary' : 'default'"
          :secondary="mode !== 'preview'"
          @click="mode = 'preview'"
        >
          排版预览
        </NButton>
      </NSpace>
    </div>

    <NInput
      v-if="mode === 'edit'"
      v-model:value="model"
      type="textarea"
      size="small"
      :placeholder="
        placeholder ??
        (variant === 'stem'
          ? '题干，支持 **加粗**、分段与 <u>下划线</u>'
          : '解题思路，支持 **加粗** 与列表')
      "
      :autosize="{ minRows: minRows ?? 6, maxRows: maxRows ?? 18 }"
    />
    <div v-else class="formatted-analysis--panel formatted-analysis--panel--fill">
      <FormattedAnalysis
        :text="model"
        :variant="variant ?? 'analysis'"
        :empty-text="emptyText ?? (variant === 'stem' ? '暂无题干' : '暂无解题思路')"
      />
    </div>
  </div>
</template>

<style scoped>
.analysis-field {
  width: 100%;
}

.analysis-field__toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 6px;
}
</style>
