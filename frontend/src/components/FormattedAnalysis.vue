<script setup lang="ts">
import { computed } from "vue";
import { formatAnalysisHtml, formatStemDisplayHtml } from "../utils/analysisFormat";

const props = withDefaults(
  defineProps<{
    text: string;
    emptyText?: string;
    /** analysis：解题思路；stem：题干（含 <u> 下划线 + 相同 Markdown 规则） */
    variant?: "analysis" | "stem";
  }>(),
  { variant: "analysis" },
);

const html = computed(() =>
  props.variant === "stem" ? formatStemDisplayHtml(props.text) : formatAnalysisHtml(props.text),
);
const isEmpty = computed(() => !props.text.trim());
const rootClass = computed(() =>
  props.variant === "stem"
    ? "formatted-analysis formatted-analysis--stem"
    : "formatted-analysis",
);
</script>

<template>
  <div v-if="isEmpty" class="formatted-analysis formatted-analysis--empty">{{ emptyText ?? "—" }}</div>
  <div v-else :class="rootClass" v-html="html" />
</template>
