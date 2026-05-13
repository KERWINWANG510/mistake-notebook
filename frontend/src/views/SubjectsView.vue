<script setup lang="ts">
import { onMounted, ref } from "vue";
import { NButton, NCard, NInput, NModal, NSpace, NSpin, NTag, useMessage } from "naive-ui";
import type { Subject } from "../api/client";
import { createSubject, deleteSubject, fetchSubjects } from "../api/client";

const message = useMessage();
const loading = ref(true);
const rows = ref<Subject[]>([]);
const showAdd = ref(false);
const newName = ref("");
const newCode = ref("");

async function load() {
  loading.value = true;
  try {
    rows.value = await fetchSubjects();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}

onMounted(load);

async function remove(id: string) {
  try {
    await deleteSubject(id);
    message.success("已删除");
    await load();
  } catch (e) {
    message.error((e as Error).message);
  }
}

async function add() {
  if (!newName.value.trim()) {
    message.warning("请输入科目名称");
    return;
  }
  try {
    await createSubject({ name: newName.value.trim(), code: newCode.value.trim() || null });
    message.success("已添加");
    showAdd.value = false;
    newName.value = "";
    newCode.value = "";
    await load();
  } catch (e) {
    message.error((e as Error).message);
  }
}
</script>

<template>
  <NSpace vertical :size="16" class="page-root">
    <header class="page-header">
      <h1 class="page-header__title">科目管理</h1>
      <p class="page-header__desc">维护错题分类用的科目列表；内置科目不可删除。</p>
    </header>
    <NCard class="surface-card" title="科目列表" :segmented="{ content: true }">
      <NSpace vertical :size="12" style="width: 100%">
        <NButton type="primary" @click="showAdd = true">新增科目</NButton>
        <NSpin :show="loading">
          <div class="entity-card-list entity-card-list--auto-grid">
            <NCard v-for="s in rows" :key="s.id" class="entity-card mistake-row-card" size="small" embedded>
              <div class="entity-card__head">
                <span class="entity-card__title">{{ s.name }}</span>
                <NTag v-if="s.is_builtin" size="small">内置</NTag>
                <NTag v-else size="small" type="info">自定义</NTag>
              </div>
              <div class="entity-card__rows">
                <div class="entity-card__row">
                  <span class="entity-card__label">编码</span>
                  <span class="entity-card__value">{{ s.code ?? "—" }}</span>
                </div>
              </div>
              <div v-if="!s.is_builtin" class="entity-card__actions">
                <NButton size="small" type="error" secondary @click="remove(s.id)">删除</NButton>
              </div>
            </NCard>
            <div v-if="!loading && rows.length === 0" class="entity-card__empty">暂无科目</div>
          </div>
        </NSpin>
      </NSpace>
    </NCard>

    <NModal v-model:show="showAdd" preset="dialog" title="新增科目" style="width: min(480px, 92vw)">
      <NSpace vertical style="width: 100%; margin-top: 12px">
        <NInput v-model:value="newName" placeholder="例如：物理、化学（必填）" />
        <NInput v-model:value="newCode" placeholder="内部编码（选填，建议小写英文，如 physics）" />
        <div class="app-actions">
          <NButton @click="showAdd = false">取消</NButton>
          <NButton type="primary" @click="add">确定</NButton>
        </div>
      </NSpace>
    </NModal>
  </NSpace>
</template>
