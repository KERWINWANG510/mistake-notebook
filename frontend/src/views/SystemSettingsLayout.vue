<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const subItems = computed(() => {
  const items = [
    { label: "个人信息", key: "/settings/profile" },
    { label: "通用设置", key: "/settings/general" },
    { label: "AI 设置", key: "/settings/ai" },
  ];
  if (auth.me?.is_admin) {
    items.push({ label: "用户管理", key: "/settings/users" });
  }
  return items;
});

const activeSubKey = computed(() => {
  const p = route.path;
  if (p.startsWith("/settings/users")) return "/settings/users";
  if (p.startsWith("/settings/ai")) return "/settings/ai";
  if (p.startsWith("/settings/general")) return "/settings/general";
  if (p.startsWith("/settings/profile")) return "/settings/profile";
  return "/settings/profile";
});

function go(key: string) {
  if (route.path !== key) router.push(key);
}
</script>

<template>
  <div class="system-settings page-root">
    <header class="page-header system-settings__header">
      <h1 class="page-header__title">系统设置</h1>
      <p class="page-header__desc">
        通用复习计划、AI 接入{{ auth.me?.is_admin ? "与系统用户账号" : "" }}；配置仅对当前登录用户生效。
      </p>
    </header>

    <nav class="system-settings__subnav" aria-label="系统设置子菜单">
      <button
        v-for="item in subItems"
        :key="item.key"
        type="button"
        class="system-settings__subnav-btn"
        :class="{ 'system-settings__subnav-btn--active': activeSubKey === item.key }"
        :aria-current="activeSubKey === item.key ? 'page' : undefined"
        @click="go(item.key)"
      >
        {{ item.label }}
      </button>
    </nav>

    <div class="system-settings__body">
      <RouterView />
    </div>
  </div>
</template>

<style scoped>
.system-settings__header {
  margin-bottom: 12px;
}

.system-settings__subnav {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
  padding: 4px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid var(--app-border, rgba(226, 232, 240, 0.92));
}

.system-settings__subnav-btn {
  flex: 1 1 auto;
  min-width: 0;
  padding: 8px 14px;
  border: none;
  border-radius: 8px;
  background: transparent;
  font-size: 13px;
  font-weight: 500;
  color: var(--app-text-muted, #64748b);
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.system-settings__subnav-btn:hover {
  color: #334155;
  background: rgba(99, 102, 241, 0.06);
}

.system-settings__subnav-btn--active {
  color: #4338ca;
  font-weight: 600;
  background: rgba(99, 102, 241, 0.12);
  box-shadow: 0 1px 2px rgba(99, 102, 241, 0.08);
}

.system-settings__body {
  width: 100%;
  min-width: 0;
}

@media (min-width: 769px) {
  .system-settings__subnav {
    display: inline-flex;
    flex-wrap: nowrap;
    max-width: 480px;
  }

  .system-settings__subnav-btn {
    flex: 1 1 0;
  }
}

@media (max-width: 768px) {
  .system-settings__subnav-btn {
    min-height: 40px;
  }
}
</style>
