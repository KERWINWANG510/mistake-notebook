<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NFormItem, NInput, NSpace, useMessage } from "naive-ui";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const route = useRoute();
const message = useMessage();
const auth = useAuthStore();

const username = ref("");
const password = ref("");
const loading = ref(false);

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
    <NCard class="login-card surface-card" :bordered="false" title="登录账号">
      <template #header-extra>
        <span style="font-size: 13px; font-weight: 400; color: var(--app-text-muted)">AI 错题本</span>
      </template>
      <NSpace vertical :size="16" style="width: 100%; margin-top: 4px">
        <NFormItem label="登录用户名">
          <NInput
            v-model:value="username"
            placeholder="请输入登录用户名（唯一，用于登录）"
            autocomplete="username"
            @keyup.enter="submit"
          />
        </NFormItem>
        <NFormItem label="密码">
          <NInput
            v-model:value="password"
            type="password"
            placeholder="请输入密码"
            show-password-on="click"
            autocomplete="current-password"
            @keyup.enter="submit"
          />
        </NFormItem>
        <NButton type="primary" block :loading="loading" @click="submit">登录</NButton>
        <p style="margin: 0; color: var(--app-text-muted); font-size: 13px; line-height: 1.5">
          演示账号：管理员 <strong>admin</strong> / 密码 <strong>123456</strong>
        </p>
      </NSpace>
    </NCard>
  </div>
</template>
