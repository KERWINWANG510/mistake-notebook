<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  NButton,
  NCard,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NInputNumber,
  NRadioButton,
  NRadioGroup,
  NSelect,
  NSpin,
  NTag,
  NUpload,
  useMessage,
} from "naive-ui";
import AvatarCropDialog from "../components/AvatarCropDialog.vue";
import UserAvatar from "../components/UserAvatar.vue";
import { useAvatarUploadPicker } from "../composables/useAvatarUploadPicker";
import {
  clearMyAvatar,
  fetchEducationStages,
  updateMyProfile,
  uploadMyAvatar,
  type EducationStageItem,
} from "../api/client";
import { GENDER_OPTIONS, genderLabel, type GenderCode } from "../constants/gender";
import { useAuthStore } from "../stores/auth";

const message = useMessage();
const auth = useAuthStore();
const loading = ref(true);
const saving = ref(false);
const pendingAvatarFile = ref<File | null>(null);
const pendingClearAvatar = ref(false);
const avatarPreviewUrl = ref<string | null>(null);
const avatarRefresh = ref(0);

const username = ref("");
const password = ref("");
const fullName = ref("");
const educationStage = ref<string | null>(null);
const enrollmentYear = ref<number | null>(null);
const gender = ref<GenderCode | null>(null);
const stages = ref<EducationStageItem[]>([]);

const stageOptions = computed(() => stages.value.map((s) => ({ label: s.name, value: s.code })));
const avatarFallback = computed(() => {
  const name = fullName.value || username.value || "?";
  return name.slice(0, 1).toUpperCase();
});
const displayName = computed(() => fullName.value.trim() || username.value || "—");
const genderText = computed(() => genderLabel(gender.value));

const profileHasCustomAvatar = computed(() => {
  if (pendingClearAvatar.value) return false;
  if (pendingAvatarFile.value) return true;
  return !!auth.me?.has_custom_avatar;
});

const profileAvatarPreview = computed(() => avatarPreviewUrl.value);

const avatarDirty = computed(() => pendingClearAvatar.value || !!pendingAvatarFile.value);

function revokeAvatarPreview() {
  if (avatarPreviewUrl.value) {
    URL.revokeObjectURL(avatarPreviewUrl.value);
    avatarPreviewUrl.value = null;
  }
}

function resetAvatarDraft() {
  revokeAvatarPreview();
  pendingAvatarFile.value = null;
  pendingClearAvatar.value = false;
}

function setPendingAvatar(file: File) {
  revokeAvatarPreview();
  pendingAvatarFile.value = file;
  pendingClearAvatar.value = false;
  avatarPreviewUrl.value = URL.createObjectURL(file);
  message.info("头像已选好，请点击保存资料后生效");
}

function queueClearAvatar() {
  revokeAvatarPreview();
  pendingAvatarFile.value = null;
  pendingClearAvatar.value = true;
  message.info("将恢复默认头像，请点击保存资料后生效");
}

function syncFromMe() {
  const me = auth.me;
  if (!me) return;
  username.value = me.username;
  fullName.value = me.full_name ?? "";
  educationStage.value = me.education_stage;
  enrollmentYear.value = me.enrollment_year;
  gender.value = (me.gender as GenderCode | null) ?? null;
  resetAvatarDraft();
}

async function load() {
  loading.value = true;
  try {
    await auth.fetchMe();
    syncFromMe();
    stages.value = await fetchEducationStages();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}

onMounted(load);

async function save() {
  if (!username.value.trim()) {
    message.warning("请输入登录用户名");
    return;
  }
  if (!fullName.value.trim()) {
    message.warning("请输入用户姓名");
    return;
  }
  if (!educationStage.value) {
    message.warning("请选择教育阶段");
    return;
  }
  if (enrollmentYear.value == null || Number.isNaN(enrollmentYear.value)) {
    message.warning("请输入入学年份");
    return;
  }
  if (password.value && password.value.length < 4) {
    message.warning("新密码至少 4 位");
    return;
  }
  saving.value = true;
  try {
    if (pendingClearAvatar.value) {
      auth.me = await clearMyAvatar();
    } else if (pendingAvatarFile.value) {
      auth.me = await uploadMyAvatar(pendingAvatarFile.value);
    }

    const payload: Parameters<typeof updateMyProfile>[0] = {
      username: username.value.trim(),
      full_name: fullName.value.trim(),
      education_stage: educationStage.value,
      enrollment_year: enrollmentYear.value,
      gender: gender.value,
    };
    if (password.value) payload.password = password.value;
    const updated = await updateMyProfile(payload);
    auth.me = updated;
    password.value = "";
    resetAvatarDraft();
    avatarRefresh.value += 1;
    message.success("已保存");
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    saving.value = false;
  }
}

const {
  cropOpen,
  cropFile,
  onUploadChange: onAvatarPick,
  onCropConfirm,
  onCropOpenChange,
} = useAvatarUploadPicker(setPendingAvatar, { deferSave: true });

onBeforeUnmount(revokeAvatarPreview);
</script>

<template>
  <NSpin :show="loading">
    <div class="user-profile page-root page-root--fixed-actions">
      <header class="user-profile__page-head">
        <h2 class="user-profile__title">个人信息</h2>
        <p class="user-profile__subtitle">管理头像、性别与账号资料，保存后全站生效。</p>
      </header>

      <section v-if="auth.me" class="user-profile__hero">
        <div class="user-profile__hero-bg" aria-hidden="true" />
        <div class="user-profile__hero-main">
          <div class="user-profile__avatar-shell">
            <UserAvatar
              :user-id="auth.me.id"
              :gender="gender"
              :has-custom-avatar="profileHasCustomAvatar"
              :preview-src="profileAvatarPreview"
              :size="88"
              :fallback-text="avatarFallback"
              :refresh-key="avatarRefresh"
            />
          </div>
          <div class="user-profile__hero-meta">
            <div class="user-profile__hero-name-row">
              <h3 class="user-profile__hero-name">{{ displayName }}</h3>
              <NTag v-if="auth.me.is_admin" size="small" round :bordered="false" class="user-profile__admin-tag">
                管理员
              </NTag>
            </div>
            <p class="user-profile__hero-login">@{{ username }}</p>
            <p class="user-profile__hero-gender">性别：{{ genderText }}</p>
          </div>
        </div>
        <div class="user-profile__hero-panel">
          <NFormItem label="性别" :show-feedback="false" label-placement="top" class="user-profile__field">
            <NRadioGroup v-model:value="gender" name="profile-gender" size="small" :disabled="saving">
              <NRadioButton :value="null">未设置</NRadioButton>
              <NRadioButton v-for="opt in GENDER_OPTIONS" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </NRadioButton>
            </NRadioGroup>
          </NFormItem>
          <div class="user-profile__hero-actions">
            <NUpload
              :show-file-list="false"
              accept="image/jpeg,image/png,image/webp,image/gif,.jpg,.jpeg,.png,.webp,.gif"
              :disabled="saving"
              @change="onAvatarPick"
            >
              <NButton type="primary" size="small" :disabled="saving">上传头像</NButton>
            </NUpload>
            <NButton
              v-if="profileHasCustomAvatar"
              size="small"
              secondary
              :disabled="saving"
              @click="queueClearAvatar"
            >
              恢复默认
            </NButton>
          </div>
          <p v-if="avatarDirty" class="user-profile__hero-tip user-profile__hero-tip--pending">头像变更未保存</p>
          <p v-else class="user-profile__hero-tip">静态图支持裁切与缩放；GIF 按原图上传，均需保存后生效。</p>
        </div>
      </section>

      <NCard class="surface-card user-profile__card" :bordered="false">
        <template #header>
          <div class="user-profile__card-head">
            <span class="user-profile__card-title">账号资料</span>
            <span class="user-profile__card-desc">登录与教育信息</span>
          </div>
        </template>
        <NGrid cols="1 s:2" :x-gap="16" :y-gap="8" responsive="screen">
          <NGridItem>
            <NFormItem label="登录用户名" :show-feedback="false" label-placement="top" class="user-profile__field">
              <NInput
                v-model:value="username"
                placeholder="用于登录，唯一"
                :disabled="saving"
                maxlength="64"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="用户姓名" :show-feedback="false" label-placement="top" class="user-profile__field">
              <NInput v-model:value="fullName" placeholder="展示名称" :disabled="saving" maxlength="64" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="教育阶段" :show-feedback="false" label-placement="top" class="user-profile__field">
              <NSelect
                v-model:value="educationStage"
                :options="stageOptions"
                placeholder="请选择"
                :disabled="saving"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="入学年份" :show-feedback="false" label-placement="top" class="user-profile__field">
              <NInputNumber
                v-model:value="enrollmentYear"
                :min="1980"
                :max="2050"
                placeholder="例如 2024"
                style="width: 100%"
                :disabled="saving"
              />
            </NFormItem>
          </NGridItem>
        </NGrid>
      </NCard>

      <NCard class="surface-card user-profile__card user-profile__card--security" :bordered="false">
        <template #header>
          <div class="user-profile__card-head">
            <span class="user-profile__card-title">安全</span>
            <span class="user-profile__card-desc">留空表示不修改密码</span>
          </div>
        </template>
        <NFormItem label="新密码" :show-feedback="false" label-placement="top" class="user-profile__field">
          <NInput
            v-model:value="password"
            type="password"
            show-password-on="click"
            placeholder="不少于 4 位"
            :disabled="saving"
            maxlength="128"
          />
        </NFormItem>
      </NCard>

    </div>

    <Teleport to="body">
      <footer class="app-actions app-actions--bar app-actions--fixed">
        <div class="app-actions--fixed-inner">
          <NButton
            type="primary"
            size="small"
            :loading="saving"
            :disabled="loading"
            @click="save"
          >
            保存资料
          </NButton>
        </div>
      </footer>
    </Teleport>

    <AvatarCropDialog
      :show="cropOpen"
      :file="cropFile"
      @update:show="onCropOpenChange"
      @confirm="onCropConfirm"
    />
  </NSpin>
</template>

<style scoped>
.user-profile {
  width: 100%;
  max-width: 640px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.user-profile__page-head {
  margin: 0;
}

.user-profile__title {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.user-profile__subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--app-text-muted, #64748b);
}

.user-profile__hero {
  position: relative;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: #fff;
  box-shadow: var(--app-shadow, 0 4px 24px rgba(15, 23, 42, 0.06));
}

.user-profile__hero-bg {
  display: block;
  width: 100%;
  height: 104px;
  background: linear-gradient(125deg, #6366f1 0%, #8b5cf6 42%, #c4b5fd 100%);
}

.user-profile__hero-main {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 16px;
  margin-top: -44px;
  padding: 0 20px 16px;
  background: #fff;
}

.user-profile__avatar-shell {
  --profile-avatar-size: 88px;
  --profile-avatar-ring: 4px;
  width: calc(var(--profile-avatar-size) + var(--profile-avatar-ring) * 2);
  height: calc(var(--profile-avatar-size) + var(--profile-avatar-ring) * 2);
  min-width: calc(var(--profile-avatar-size) + var(--profile-avatar-ring) * 2);
  min-height: calc(var(--profile-avatar-size) + var(--profile-avatar-ring) * 2);
  flex-shrink: 0;
  padding: var(--profile-avatar-ring);
  box-sizing: border-box;
  display: grid;
  place-items: center;
  border-radius: 50%;
  overflow: hidden;
  aspect-ratio: 1;
  background: linear-gradient(145deg, #6366f1, #8b5cf6);
  box-shadow: 0 10px 28px rgba(99, 102, 241, 0.35);
}

.user-profile__avatar-shell :deep(.user-avatar) {
  width: var(--profile-avatar-size) !important;
  height: var(--profile-avatar-size) !important;
  min-width: var(--profile-avatar-size);
  min-height: var(--profile-avatar-size);
  flex-shrink: 0;
  border-radius: 50%;
  overflow: hidden;
  box-shadow: 0 0 0 3px #fff;
}

.user-profile__hero-meta {
  flex: 1;
  min-width: min(100%, 180px);
  padding: 8px 0 6px;
}

.user-profile__hero-name-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.user-profile__hero-name {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
  line-height: 1.3;
  word-break: break-word;
}

.user-profile__admin-tag {
  background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
  color: #fff !important;
  font-weight: 600;
}

.user-profile__hero-login {
  margin: 6px 0 0;
  font-size: 13px;
  font-weight: 500;
  color: #334155;
  word-break: break-all;
}

.user-profile__hero-gender {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
}

.user-profile__hero-panel {
  position: relative;
  padding: 16px 20px 18px;
  background: #f1f5f9;
  border-top: 1px solid rgba(148, 163, 184, 0.22);
}

.user-profile__hero-actions {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}

.user-profile__hero-tip {
  margin: 10px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--app-text-subtle, #94a3b8);
}

.user-profile__hero-tip--pending {
  color: #4f46e5;
  font-weight: 500;
}

@media (max-width: 768px) {
  .user-profile__hero-actions {
    flex-wrap: wrap;
  }
}

.user-profile__card :deep(.n-card-header) {
  padding-bottom: 8px;
}

.user-profile__card :deep(.n-card__content) {
  padding-top: 4px;
}

.user-profile__card-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-profile__card-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.user-profile__card-desc {
  font-size: 12px;
  color: var(--app-text-muted, #64748b);
}

.user-profile__field {
  margin-bottom: 0;
  width: 100%;
}

.user-profile__field :deep(.n-form-item-label) {
  padding-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}

.user-profile__card--security {
  margin-top: 0;
}

@media (max-width: 768px) {
  .user-profile__hero-bg {
    height: 88px;
  }

  .user-profile__hero-main {
    margin-top: -36px;
    padding: 0 16px 14px;
  }

  .user-profile__hero-panel {
    padding: 14px 16px 16px;
  }

}
</style>
