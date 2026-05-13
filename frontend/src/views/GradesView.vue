<script setup lang="ts">
import { onMounted, ref } from "vue";
import { NButton, NCard, NInput, NInputNumber, NModal, NSpace, NSpin, NTag, useMessage } from "naive-ui";
import type { Grade } from "../api/client";
import { createGrade, deleteGrade, fetchGrades } from "../api/client";

const message = useMessage();
const loading = ref(true);
const rows = ref<Grade[]>([]);
const showAdd = ref(false);
const newLevel = ref<number | null>(10);
const newName = ref("");

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

async function remove(id: string) {
  try {
    await deleteGrade(id);
    message.success("已删除");
    await load();
  } catch (e) {
    message.error((e as Error).message);
  }
}

async function add() {
  if (newLevel.value == null) {
    message.warning("请输入年级序号");
    return;
  }
  if (!newName.value.trim()) {
    message.warning("请输入展示名称");
    return;
  }
  try {
    await createGrade({ level: newLevel.value, name: newName.value.trim() });
    message.success("已添加");
    showAdd.value = false;
    newName.value = "";
    await load();
  } catch (e) {
    message.error((e as Error).message);
  }
}
</script>

<template>
  <NSpace vertical :size="16" class="page-root">
    <header class="page-header">
      <h1 class="page-header__title">年级管理</h1>
      <p class="page-header__desc">年级用于筛选与归类；序号越小通常表示越低年级。</p>
    </header>
    <NCard class="surface-card" title="年级列表" :segmented="{ content: true }">
      <NSpace vertical :size="12" style="width: 100%">
        <NButton type="primary" @click="showAdd = true">新增年级</NButton>
        <NSpin :show="loading">
          <div class="entity-card-list entity-card-list--auto-grid">
            <NCard v-for="g in rows" :key="g.id" class="entity-card mistake-row-card" size="small" embedded>
              <div class="entity-card__head">
                <span class="entity-card__title">{{ g.name }}</span>
                <NTag v-if="g.is_builtin" size="small">内置</NTag>
                <NTag v-else size="small" type="info">自定义</NTag>
              </div>
              <div class="entity-card__rows">
                <div class="entity-card__row">
                  <span class="entity-card__label">序号</span>
                  <span class="entity-card__value">{{ g.level }}</span>
                </div>
              </div>
              <div v-if="!g.is_builtin" class="entity-card__actions">
                <NButton size="small" type="error" secondary @click="remove(g.id)">删除</NButton>
              </div>
            </NCard>
            <div v-if="!loading && rows.length === 0" class="entity-card__empty">暂无年级</div>
          </div>
        </NSpin>
      </NSpace>
    </NCard>

    <NModal v-model:show="showAdd" preset="dialog" title="新增年级" style="width: min(480px, 92vw)">
      <NSpace vertical style="width: 100%; margin-top: 12px">
        <NInputNumber
          v-model:value="newLevel"
          :min="1"
          :max="20"
          placeholder="数字序号，如 10 表示高一"
          style="width: 100%"
        />
        <NInput v-model:value="newName" placeholder="界面展示名称，如「高一」「初二」" />
        <NSpace justify="end">
          <NButton @click="showAdd = false">取消</NButton>
          <NButton type="primary" @click="add">确定</NButton>
        </NSpace>
      </NSpace>
    </NModal>
  </NSpace>
</template>
