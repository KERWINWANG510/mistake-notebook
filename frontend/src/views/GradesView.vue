<script setup lang="ts">
import { onMounted, ref } from "vue";
import { NCard, NSpace, NSpin, useMessage } from "naive-ui";
import type { Grade } from "../api/client";
import { fetchGrades } from "../api/client";

const message = useMessage();
const loading = ref(true);
const rows = ref<Grade[]>([]);

async function load() {
  loading.value = true;
  try {
    rows.value = await fetchGrades();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <NSpace vertical :size="16" class="page-root">
    <header class="page-header">
      <h1 class="page-header__title">年级</h1>
      <p class="page-header__desc">
        系统内置一至九年级与高一至高三，共 12 个年级，用于错题筛选与归类；不支持新增、修改或删除。
      </p>
    </header>
    <NCard class="surface-card" title="年级列表" :segmented="{ content: true }">
      <NSpin :show="loading">
        <div class="entity-card-list entity-card-list--auto-grid">
          <NCard v-for="g in rows" :key="g.id" class="entity-card mistake-row-card" size="small" embedded>
            <div class="entity-card__head">
              <span class="entity-card__title">{{ g.name }}</span>
            </div>
            <div class="entity-card__rows">
              <div class="entity-card__row">
                <span class="entity-card__label">序号</span>
                <span class="entity-card__value">{{ g.level }}</span>
              </div>
            </div>
          </NCard>
          <div v-if="!loading && rows.length === 0" class="entity-card__empty">暂无年级数据</div>
        </div>
      </NSpin>
    </NCard>
  </NSpace>
</template>
