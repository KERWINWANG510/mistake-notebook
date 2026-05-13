<script setup lang="ts">
import { computed } from "vue";
import { formatAnalysisHtml } from "../utils/analysisFormat";

const props = defineProps<{
  text: string;
  emptyText?: string;
}>();

const html = computed(() => formatAnalysisHtml(props.text));
const isEmpty = computed(() => !props.text.trim());
</script>

<template>
  <div v-if="isEmpty" class="formatted-analysis formatted-analysis--empty">{{ emptyText ?? "—" }}</div>
  <div v-else class="formatted-analysis" v-html="html" />
</template>
