<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NFormItem, NInput, useMessage } from "naive-ui";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const route = useRoute();
const message = useMessage();
const auth = useAuthStore();

const username = ref("");
const password = ref("");
const loading = ref(false);

const features = [
  { label: "拍照识题", desc: "流式解析题干与思路" },
  { label: "举一反三", desc: "AI 生成练习并批改" },
  { label: "错题统计", desc: "年级科目与知识点分布" },
];

async function submit() {
  if (!username.value.trim() || !password.value) {
    message.warning("请输入登录用户名和密码");
    return;
  }
  loading.value = true;
  try {
    await auth.login(username.value.trim(), password.value);
    message.success("登录成功");
    const redir = typeof route.query.redirect === "string" ? route.query.redirect : "/mistakes";
    router.replace(redir || "/mistakes");
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-page__bg" aria-hidden="true">
      <span class="login-page__orb login-page__orb--1" />
      <span class="login-page__orb login-page__orb--2" />
      <span class="login-page__orb login-page__orb--3" />
    </div>

    <div class="login-shell surface-card">
      <section class="login-brand" aria-label="产品介绍">
        <div class="login-brand__mark" aria-hidden="true">错</div>
        <h1 class="login-brand__title">AI 错题本</h1>
        <p class="login-brand__tagline">整理错题、智能练习、用数据看清薄弱点</p>
        <ul class="login-brand__features">
          <li v-for="item in features" :key="item.label" class="login-brand__feature">
            <span class="login-brand__feature-dot" aria-hidden="true" />
            <span class="login-brand__feature-text">
              <strong>{{ item.label }}</strong>
              <span>{{ item.desc }}</span>
            </span>
          </li>
        </ul>
      </section>

      <section class="login-form-panel">
        <header class="login-form-panel__head">
          <h2 class="login-form-panel__title">欢迎回来</h2>
          <p class="login-form-panel__desc">登录你的账号以继续使用</p>
        </header>

        <form class="login-form" @submit.prevent="submit">
          <NFormItem label="登录用户名" :show-feedback="false">
            <NInput
              v-model:value="username"
              size="large"
              clearable
              placeholder="用户名"
              autocomplete="username"
              @keyup.enter="submit"
            >
              <template #prefix>
                <span class="login-field-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
                    <path d="M20 21a8 8 0 1 0-16 0" stroke-linecap="round" />
                    <circle cx="12" cy="8" r="4" />
                  </svg>
                </span>
              </template>
            </NInput>
          </NFormItem>
          <NFormItem label="密码" :show-feedback="false">
            <NInput
              v-model:value="password"
              type="password"
              size="large"
              clearable
              placeholder="密码"
              show-password-on="click"
              autocomplete="current-password"
              @keyup.enter="submit"
            >
              <template #prefix>
                <span class="login-field-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
                    <rect x="5" y="11" width="14" height="10" rx="2" />
                    <path d="M8 11V8a4 4 0 1 1 8 0v3" stroke-linecap="round" />
                  </svg>
                </span>
              </template>
            </NInput>
          </NFormItem>
          <NButton
            type="primary"
            size="large"
            block
            attr-type="submit"
            class="login-form__submit"
            :loading="loading"
          >
            登录
          </NButton>
        </form>
      </section>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: max(20px, env(safe-area-inset-top)) 16px max(28px, env(safe-area-inset-bottom));
  overflow: hidden;
  background:
    radial-gradient(ellipse 90% 70% at 10% -10%, rgba(99, 102, 241, 0.28), transparent 55%),
    radial-gradient(ellipse 70% 55% at 100% 100%, rgba(139, 92, 246, 0.2), transparent 50%),
    linear-gradient(165deg, #eef2ff 0%, #f4f6fb 42%, #e8ecff 100%);
}

.login-page__bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.login-page__orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(48px);
  opacity: 0.55;
  animation: login-orb-float 14s ease-in-out infinite;
}

.login-page__orb--1 {
  width: min(420px, 70vw);
  height: min(420px, 70vw);
  top: -12%;
  right: -8%;
  background: rgba(99, 102, 241, 0.35);
}

.login-page__orb--2 {
  width: min(320px, 55vw);
  height: min(320px, 55vw);
  bottom: -8%;
  left: -6%;
  background: rgba(139, 92, 246, 0.28);
  animation-delay: -4s;
}

.login-page__orb--3 {
  width: min(200px, 40vw);
  height: min(200px, 40vw);
  top: 42%;
  left: 38%;
  background: rgba(59, 130, 246, 0.18);
  animation-delay: -7s;
}

@keyframes login-orb-float {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }
  50% {
    transform: translate(12px, -16px) scale(1.04);
  }
}

.login-shell {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 920px;
  display: grid;
  grid-template-columns: 1fr;
  border-radius: 24px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.75);
  box-shadow:
    0 0 0 1px rgba(99, 102, 241, 0.06),
    0 24px 64px rgba(15, 23, 42, 0.12),
    0 8px 24px rgba(99, 102, 241, 0.08);
}

.login-brand {
  position: relative;
  padding: 32px 28px 28px;
  color: #fff;
  background:
    radial-gradient(ellipse 120% 90% at 0% 0%, rgba(255, 255, 255, 0.18), transparent 50%),
    linear-gradient(145deg, #4f46e5 0%, #6366f1 42%, #7c3aed 100%);
  overflow: hidden;
}

.login-brand::after {
  content: "";
  position: absolute;
  inset: 0;
  background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.06'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
  opacity: 0.9;
  pointer-events: none;
}

.login-brand > * {
  position: relative;
  z-index: 1;
}

.login-brand__mark {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: #4f46e5;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.18);
  margin-bottom: 20px;
}

.login-brand__title {
  margin: 0 0 10px;
  font-size: clamp(1.5rem, 4vw, 1.85rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.2;
}

.login-brand__tagline {
  margin: 0 0 24px;
  font-size: 14px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.88);
  max-width: 28em;
}

.login-brand__features {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.login-brand__feature {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.login-brand__feature-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  margin-top: 7px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.2);
}

.login-brand__feature-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 13px;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.82);
}

.login-brand__feature-text strong {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.login-form-panel {
  padding: 28px 24px 32px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.login-form-panel__head {
  margin-bottom: 22px;
}

.login-form-panel__title {
  margin: 0 0 6px;
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #0f172a;
}

.login-form-panel__desc {
  margin: 0;
  font-size: 14px;
  color: var(--app-text-muted);
  line-height: 1.5;
}

.login-form {
  width: 100%;
}

.login-form :deep(.n-form-item) {
  margin-bottom: 4px;
}

.login-form :deep(.n-form-item-label) {
  font-weight: 600;
  color: #334155;
  padding-bottom: 6px;
}

.login-form :deep(.n-input) {
  --n-border: 1px solid rgba(148, 163, 184, 0.45);
  --n-border-hover: 1px solid rgba(99, 102, 241, 0.45);
  --n-border-focus: 1px solid #6366f1;
  --n-box-shadow-focus: 0 0 0 3px rgba(99, 102, 241, 0.15);
}

.login-field-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  color: #94a3b8;
}

.login-field-icon svg {
  width: 18px;
  height: 18px;
}

.login-form__submit {
  margin-top: 8px;
  height: 44px !important;
  font-size: 15px !important;
  font-weight: 600 !important;
  border-radius: 12px !important;
  box-shadow: 0 8px 22px rgba(79, 70, 229, 0.28);
}

.login-form__submit:not(:disabled):hover {
  box-shadow: 0 10px 28px rgba(79, 70, 229, 0.34);
}

@media (min-width: 768px) {
  .login-page {
    padding: 32px 24px;
  }

  .login-shell {
    grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
    min-height: 480px;
  }

  .login-brand {
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 44px 40px;
  }

  .login-form-panel {
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 44px 40px 48px;
  }

  .login-form-panel__head {
    margin-bottom: 26px;
  }
}

@media (max-width: 767px) {
  .login-shell {
    border-radius: 20px;
  }

  .login-brand__features {
    display: none;
  }

  .login-brand {
    padding: 24px 22px 20px;
    text-align: center;
  }

  .login-brand__mark {
    margin-left: auto;
    margin-right: auto;
    margin-bottom: 14px;
    width: 44px;
    height: 44px;
    font-size: 18px;
  }

  .login-brand__title {
    font-size: 1.35rem;
    margin-bottom: 6px;
  }

  .login-brand__tagline {
    margin-bottom: 0;
    font-size: 13px;
  }
}
</style>
