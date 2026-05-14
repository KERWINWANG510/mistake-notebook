<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { MenuOption } from "naive-ui";
import { NIcon } from "naive-ui";
import NavIcon from "./components/NavIcon.vue";
import { useAuthStore } from "./stores/auth";
import { themeOverrides } from "./naive-theme";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();

const narrow = ref(false);
const windowWidth = ref(typeof window !== "undefined" ? window.innerWidth : 360);
function updateNarrow() {
  narrow.value = window.matchMedia("(max-width: 768px)").matches;
  windowWidth.value = window.innerWidth;
}
onMounted(() => {
  updateNarrow();
  window.addEventListener("resize", updateNarrow);
  void auth.fetchMe();
});
onUnmounted(() => window.removeEventListener("resize", updateNarrow));

const drawerOpen = ref(false);

const drawerWidth = computed(() => Math.min(320, Math.round(windowWidth.value * 0.88)));

type NavItem = {
  label: string;
  key: string;
  icon: "book" | "subject" | "grade" | "ai" | "users" | "stats";
};

const navItems = computed<NavItem[]>(() => {
  const items: NavItem[] = [
    { label: "错题本", key: "/mistakes", icon: "book" },
    { label: "统计", key: "/stats", icon: "stats" },
    { label: "年级科目", key: "/grade-subjects", icon: "subject" },
    { label: "AI 设置", key: "/settings/ai", icon: "ai" },
  ];
  if (auth.me?.is_admin) {
    items.push({ label: "用户管理", key: "/admin/users", icon: "users" });
  }
  return items;
});

const menuOptions = computed<MenuOption[]>(() =>
  navItems.value.map((item) => ({
    label: item.label,
    key: item.key,
    icon: () => h(NIcon, null, { default: () => h(NavIcon, { name: item.icon }) }),
  })),
);

const activeKey = computed(() => {
  const p = route.path;
  if (p.startsWith("/mistakes")) return "/mistakes";
  if (p.startsWith("/stats")) return "/stats";
  if (p.startsWith("/admin")) return p;
  return p;
});

const userInitial = computed(() => {
  const name = auth.me?.full_name || auth.me?.username || "?";
  return name.slice(0, 1).toUpperCase();
});

function go(key: string) {
  router.push(key);
  drawerOpen.value = false;
}

function logout() {
  drawerOpen.value = false;
  auth.logout();
  router.replace("/login");
}
</script>

<template>
  <NConfigProvider :theme-overrides="themeOverrides">
    <NMessageProvider>
      <NDialogProvider>
        <RouterView v-if="route.path === '/login'" />
        <template v-else>
          <NLayout class="app-shell" style="background: transparent">
            <NLayoutHeader
              class="app-header"
              bordered
              :style="{ height: narrow ? '52px' : '58px', padding: narrow ? '0 12px' : '0 16px' }"
            >
              <div class="app-header-inner" style="height: 100%">
                <div class="app-brand">
                  <div class="app-brand__mark">错</div>
                  <div class="app-brand__text">AI 错题本</div>
                  <NMenu
                    v-if="!narrow && auth.isLoggedIn"
                    mode="horizontal"
                    :value="activeKey"
                    :options="menuOptions"
                    style="flex: 1; min-width: 0; margin-left: 8px"
                    @update:value="go"
                  />
                </div>
                <NSpace align="center" :size="8" :wrap="narrow">
                  <NText v-if="auth.me && !narrow" depth="3" style="font-size: 13px">
                    你好，{{ auth.me.full_name || auth.me.username }}
                  </NText>
                  <NButton v-if="auth.isLoggedIn && !narrow" size="small" secondary @click="logout">退出</NButton>
                  <NButton
                    v-if="narrow && auth.isLoggedIn"
                    class="app-menu-trigger"
                    quaternary
                    circle
                    aria-label="打开菜单"
                    @click="drawerOpen = true"
                  >
                    <NavIcon name="menu" />
                  </NButton>
                </NSpace>
              </div>
            </NLayoutHeader>
            <NLayoutContent class="app-content" :native-scrollbar="false">
              <RouterView :key="route.fullPath" />
            </NLayoutContent>
          </NLayout>

          <NDrawer
            v-model:show="drawerOpen"
            class="app-nav-drawer"
            placement="left"
            :width="drawerWidth"
            display-directive="show"
          >
            <NDrawerContent :native-scrollbar="false" body-content-style="padding: 0" :header-style="{ display: 'none' }">
              <div class="app-nav-drawer__panel">
                <div class="app-nav-drawer__hero">
                  <div class="app-nav-drawer__hero-bg" aria-hidden="true" />
                  <div class="app-nav-drawer__profile">
                    <div class="app-nav-drawer__avatar">{{ userInitial }}</div>
                    <div class="app-nav-drawer__profile-text">
                      <div class="app-nav-drawer__app-name">AI 错题本</div>
                      <div v-if="auth.me" class="app-nav-drawer__user-name">
                        {{ auth.me.full_name || auth.me.username }}
                      </div>
                    </div>
                  </div>
                </div>

                <nav class="app-nav-drawer__nav" aria-label="主导航">
                  <button
                    v-for="item in navItems"
                    :key="item.key"
                    type="button"
                    class="app-nav-drawer__item"
                    :class="{ 'app-nav-drawer__item--active': activeKey === item.key }"
                    @click="go(item.key)"
                  >
                    <span class="app-nav-drawer__item-icon">
                      <NavIcon :name="item.icon" />
                    </span>
                    <span class="app-nav-drawer__item-label">{{ item.label }}</span>
                    <span class="app-nav-drawer__item-arrow" aria-hidden="true">›</span>
                  </button>
                </nav>

                <div class="app-nav-drawer__footer">
                  <NButton class="app-nav-drawer__logout" block secondary strong @click="logout">
                    <template #icon>
                      <NavIcon name="logout" />
                    </template>
                    退出登录
                  </NButton>
                </div>
              </div>
            </NDrawerContent>
          </NDrawer>
        </template>
      </NDialogProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>
