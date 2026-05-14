<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  NButton,
  NCard,
  NInput,
  NInputNumber,
  NModal,
  NPopconfirm,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  NTag,
  useMessage,
} from "naive-ui";
import {
  createUserAccount,
  deleteUserAccount,
  fetchEducationStages,
  fetchUserList,
  updateUserAccount,
  type EducationStageItem,
  type MeUser,
} from "../api/client";
import { useAuthStore } from "../stores/auth";

const message = useMessage();
const auth = useAuthStore();
const rows = ref<MeUser[]>([]);
const stages = ref<EducationStageItem[]>([]);
const loading = ref(true);
const showAdd = ref(false);
const showEdit = ref(false);
const editingUser = ref<MeUser | null>(null);

const newUsername = ref("");
const newPassword = ref("");
const newFullName = ref("");
const newEducationStage = ref<string | null>(null);
const newEnrollmentYear = ref<number>(new Date().getFullYear());

const editUsername = ref("");
const editPassword = ref("");
const editFullName = ref("");
const editEducationStage = ref<string | null>(null);
const editEnrollmentYear = ref<number | null>(null);
const editIsAdmin = ref(false);

const stageOptions = computed(() => stages.value.map((s) => ({ label: s.name, value: s.code })));

function stageLabel(code: string | null | undefined): string {
  if (!code) return "—";
  return stages.value.find((s) => s.code === code)?.name ?? code;
}

function isSelf(user: MeUser) {
  return user.id === auth.me?.id;
}

async function load() {
  loading.value = true;
  try {
    const [list, st] = await Promise.all([fetchUserList(), fetchEducationStages()]);
    rows.value = list;
    stages.value = st;
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}

onMounted(load);

async function add() {
  if (!newUsername.value.trim()) {
    message.warning("请输入登录用户名");
    return;
  }
  if (!newFullName.value.trim()) {
    message.warning("请输入用户姓名");
    return;
  }
  if (!newEducationStage.value) {
    message.warning("请选择教育阶段");
    return;
  }
  if (newEnrollmentYear.value == null || Number.isNaN(newEnrollmentYear.value)) {
    message.warning("请输入入学年份");
    return;
  }
  if (newPassword.value.length < 4) {
    message.warning("密码至少 4 位");
    return;
  }
  try {
    await createUserAccount({
      username: newUsername.value.trim(),
      password: newPassword.value,
      full_name: newFullName.value.trim(),
      education_stage: newEducationStage.value,
      enrollment_year: newEnrollmentYear.value,
    });
    message.success("已创建用户");
    showAdd.value = false;
    newUsername.value = "";
    newPassword.value = "";
    newFullName.value = "";
    newEducationStage.value = null;
    newEnrollmentYear.value = new Date().getFullYear();
    await load();
  } catch (e) {
    message.error((e as Error).message);
  }
}

function openAddModal() {
  newEnrollmentYear.value = new Date().getFullYear();
  showAdd.value = true;
}

function openEditModal(user: MeUser) {
  editingUser.value = user;
  editUsername.value = user.username;
  editFullName.value = user.full_name ?? "";
  editEducationStage.value = user.education_stage;
  editEnrollmentYear.value = user.enrollment_year;
  editIsAdmin.value = user.is_admin;
  editPassword.value = "";
  showEdit.value = true;
}

async function saveEdit() {
  if (!editingUser.value) return;
  if (!editUsername.value.trim()) {
    message.warning("请输入登录用户名");
    return;
  }
  if (!editFullName.value.trim()) {
    message.warning("请输入用户姓名");
    return;
  }
  if (!editEducationStage.value) {
    message.warning("请选择教育阶段");
    return;
  }
  if (editEnrollmentYear.value == null || Number.isNaN(editEnrollmentYear.value)) {
    message.warning("请输入入学年份");
    return;
  }
  if (editPassword.value && editPassword.value.length < 4) {
    message.warning("新密码至少 4 位");
    return;
  }
  try {
    const userId = editingUser.value.id;
    const payload: Parameters<typeof updateUserAccount>[1] = {
      username: editUsername.value.trim(),
      full_name: editFullName.value.trim(),
      education_stage: editEducationStage.value,
      enrollment_year: editEnrollmentYear.value,
      is_admin: editIsAdmin.value,
    };
    if (editPassword.value) {
      payload.password = editPassword.value;
    }
    await updateUserAccount(userId, payload);
    message.success("已保存");
    showEdit.value = false;
    editingUser.value = null;
    await load();
    if (userId === auth.me?.id) {
      await auth.fetchMe();
    }
  } catch (e) {
    message.error((e as Error).message);
  }
}

async function remove(user: MeUser) {
  try {
    await deleteUserAccount(user.id);
    message.success("已删除");
    await load();
  } catch (e) {
    message.error((e as Error).message);
  }
}
</script>

<template>
  <NSpace vertical :size="16" class="page-root">
    <header class="page-header">
      <h1 class="page-header__title">用户管理</h1>
      <p class="page-header__desc">仅管理员可见；登录名为唯一登录账号，并记录姓名、教育阶段与入学年份。</p>
    </header>
    <NCard class="surface-card" title="账号列表" :segmented="{ content: true }">
      <NSpace vertical :size="12" style="width: 100%">
        <NButton type="primary" @click="openAddModal">新建用户</NButton>
        <NSpin :show="loading">
          <div class="entity-card-list entity-card-list--auto-grid">
            <NCard v-for="u in rows" :key="u.id" class="entity-card mistake-row-card" size="small" embedded>
              <div class="entity-card__head">
                <span class="entity-card__title">{{ u.full_name || u.username }}</span>
                <NTag v-if="u.is_admin" size="small" type="warning">管理员</NTag>
                <NTag v-else size="small">用户</NTag>
              </div>
              <div class="entity-card__rows">
                <div class="entity-card__row">
                  <span class="entity-card__label">登录名</span>
                  <span class="entity-card__value">{{ u.username }}</span>
                </div>
                <div class="entity-card__row">
                  <span class="entity-card__label">教育阶段</span>
                  <span class="entity-card__value">{{ stageLabel(u.education_stage) }}</span>
                </div>
                <div class="entity-card__row">
                  <span class="entity-card__label">入学年份</span>
                  <span class="entity-card__value">{{ u.enrollment_year ?? "—" }}</span>
                </div>
              </div>
              <div class="entity-card__actions">
                <NButton size="small" @click="openEditModal(u)">编辑</NButton>
                <NPopconfirm
                  v-if="!isSelf(u)"
                  positive-text="删除"
                  negative-text="取消"
                  @positive-click="remove(u)"
                >
                  <template #trigger>
                    <NButton size="small" type="error" secondary>删除</NButton>
                  </template>
                  确定删除用户「{{ u.full_name || u.username }}」？其错题数据将一并删除。
                </NPopconfirm>
              </div>
            </NCard>
            <div v-if="!loading && rows.length === 0" class="entity-card__empty">暂无用户</div>
          </div>
        </NSpin>
      </NSpace>
    </NCard>

    <NModal v-model:show="showAdd" preset="dialog" title="新建用户" style="width: min(480px, 92vw)">
      <NSpace vertical style="width: 100%; margin-top: 12px" :size="12">
        <NInput v-model:value="newUsername" placeholder="登录用户名（唯一，用于登录）" />
        <NInput v-model:value="newFullName" placeholder="用户姓名" />
        <NSelect
          v-model:value="newEducationStage"
          :options="stageOptions"
          placeholder="教育阶段（小学 / 初中 / 高中 / 大学）"
        />
        <NInputNumber
          v-model:value="newEnrollmentYear"
          :min="1980"
          :max="2050"
          placeholder="入学年份"
          style="width: 100%"
        />
        <NInput
          v-model:value="newPassword"
          type="password"
          show-password-on="click"
          placeholder="设置初始登录密码（不少于 4 位）"
        />
        <div class="app-actions">
          <NButton @click="showAdd = false">取消</NButton>
          <NButton type="primary" @click="add">确定</NButton>
        </div>
      </NSpace>
    </NModal>

    <NModal v-model:show="showEdit" preset="dialog" title="编辑用户" style="width: min(480px, 92vw)">
      <NSpace vertical style="width: 100%; margin-top: 12px" :size="12">
        <NInput v-model:value="editUsername" placeholder="登录用户名" />
        <NInput v-model:value="editFullName" placeholder="用户姓名" />
        <NSelect v-model:value="editEducationStage" :options="stageOptions" placeholder="教育阶段" />
        <NInputNumber
          v-model:value="editEnrollmentYear"
          :min="1980"
          :max="2050"
          placeholder="入学年份"
          style="width: 100%"
        />
        <NInput
          v-model:value="editPassword"
          type="password"
          show-password-on="click"
          placeholder="新密码（留空则不修改）"
        />
        <div class="users-admin__switch-row">
          <span>管理员权限</span>
          <NSwitch v-model:value="editIsAdmin" :disabled="editingUser ? isSelf(editingUser) : false" />
        </div>
        <div class="app-actions">
          <NButton @click="showEdit = false">取消</NButton>
          <NButton type="primary" @click="saveEdit">保存</NButton>
        </div>
      </NSpace>
    </NModal>
  </NSpace>
</template>

<style scoped>
.users-admin__switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 14px;
  color: #334155;
}
</style>
