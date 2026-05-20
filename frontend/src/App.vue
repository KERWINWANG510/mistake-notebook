<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NAvatar, NButton, NTooltip } from "naive-ui";
import NavIcon from "./components/NavIcon.vue";
import { fetchAppVersion } from "./api/client";
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
  void fetchAppVersion()
    .then((v) => {
      if (v?.trim()) appVersion.value = v.trim();
    })
    .catch(() => {
      /* 未登录或离线时保留构建时版本 */
    });
});
onUnmounted(() => window.removeEventListener("resize", updateNarrow));

const drawerOpen = ref(false);
const appVersion = ref(import.meta.env.VITE_APP_VERSION?.trim() || "dev");

const drawerWidth = computed(() => Math.min(320, Math.round(windowWidth.value * 0.88)));

type NavChild = {
  label: string;
  key: string;
};

type NavItem = {
  label: string;
  key: string;
  icon: "book" | "subject" | "grade" | "ai" | "users" | "stats" | "practice" | "settings" | "review";
  children?: NavChild[];
};

const settingsChildren = computed<NavChild[]>(() => {
  const children: NavChild[] = [
    { label: "通用设置", key: "/settings/general" },
    { label: "AI 设置", key: "/settings/ai" },
  ];
  if (auth.me?.is_admin) {
    children.push({ label: "用户管理", key: "/settings/users" });
  }
  return children;
});

const navItems = computed<NavItem[]>(() => [
  { label: "错题本", key: "/mistakes", icon: "book" },
  { label: "今日复习", key: "/review", icon: "review" },
  { label: "模拟卷", key: "/practice/mock-paper", icon: "practice" },
  { label: "统计", key: "/stats", icon: "stats" },
  { label: "年级科目", key: "/grade-subjects", icon: "subject" },
  {
    label: "系统设置",
    key: "/settings",
    icon: "settings",
    children: settingsChildren.value,
  },
]);

const activeKey = computed(() => {
  const p = route.path;
  if (p.startsWith("/mistakes")) return "/mistakes";
  if (p.startsWith("/review")) return "/review";
  if (p.startsWith("/practice")) return "/practice/mock-paper";
  if (p.startsWith("/stats")) return "/stats";
  if (p.startsWith("/settings")) return p;
  return p;
});

const settingsExpanded = computed(() => route.path.startsWith("/settings"));

const userInitial = computed(() => {
  const name = auth.me?.full_name || auth.me?.username || "?";
  return name.slice(0, 1).toUpperCase();
});

function go(key: string) {
  router.push(key);
  drawerOpen.value = false;
}

function navActive(item: NavItem) {
  if (item.children?.length) {
    return route.path.startsWith(item.key);
  }
  return activeKey.value === item.key;
}

function navChildActive(child: NavChild) {
  return activeKey.value === child.key;
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
              :style="{ height: narrow ? '52px' : '60px', padding: narrow ? '0 12px' : '0 14px' }"
            >
              <div class="app-header-inner" :class="{ 'app-header-inner--narrow': narrow }" style="height: 100%">
                <div class="app-header__brand">
                  <div class="app-brand__mark" aria-hidden="true">错</div>
                  <div class="app-header__brand-text">
                    <span class="app-brand__text">AI 错题本</span>
                    <span v-if="appVersion" class="app-version" :title="`版本 ${appVersion}`">v{{ appVersion }}</span>
                  </div>
                </div>

                <nav
                  v-if="!narrow && auth.isLoggedIn"
                  class="app-top-nav"
                  aria-label="主导航"
                >
                  <button
                    v-for="item in navItems"
                    :key="item.key"
                    type="button"
                    class="app-top-nav__btn"
                    :class="{ 'app-top-nav__btn--active': navActive(item) }"
                    :aria-current="navActive(item) ? 'page' : undefined"
                    @click="go(item.key)"
                  >
                    <span class="app-top-nav__ico" aria-hidden="true">
                      <NavIcon :name="item.icon" />
                    </span>
                    <span class="app-top-nav__txt">{{ item.label }}</span>
                  </button>
                </nav>

                <div class="app-header__trailing">
                  <template v-if="!narrow && auth.isLoggedIn && auth.me">
                    <NTooltip placement="bottom-end">
                      <template #trigger>
                        <span class="app-user-chip">
                          <NAvatar round :size="32" class="app-user-chip__avatar">{{ userInitial }}</NAvatar>
                        </span>
                      </template>
                      {{ auth.me.full_name || auth.me.username }}
                    </NTooltip>
                    <NButton size="small" quaternary class="app-header__logout" @click="logout">退出</NButton>
                  </template>
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
                </div>
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
                  <template v-for="item in navItems" :key="item.key">
                    <button
                      v-if="!item.children?.length"
                      type="button"
                      class="app-nav-drawer__item"
                      :class="{ 'app-nav-drawer__item--active': navActive(item) }"
                      @click="go(item.key)"
                    >
                      <span class="app-nav-drawer__item-icon">
                        <NavIcon :name="item.icon" />
                      </span>
                      <span class="app-nav-drawer__item-label">{{ item.label }}</span>
                      <span class="app-nav-drawer__item-arrow" aria-hidden="true">›</span>
                    </button>
                    <div v-else class="app-nav-drawer__group">
                      <button
                        type="button"
                        class="app-nav-drawer__item"
                        :class="{ 'app-nav-drawer__item--open': settingsExpanded }"
                        @click="go(item.children![0].key)"
                      >
                        <span class="app-nav-drawer__item-icon">
                          <NavIcon :name="item.icon" />
                        </span>
                        <span class="app-nav-drawer__item-label">{{ item.label }}</span>
                        <span class="app-nav-drawer__item-arrow" aria-hidden="true">›</span>
                      </button>
                      <button
                        v-for="child in item.children"
                        :key="child.key"
                        type="button"
                        class="app-nav-drawer__item app-nav-drawer__item--child"
                        :class="{ 'app-nav-drawer__item--active': navChildActive(child) }"
                        @click="go(child.key)"
                      >
                        <span class="app-nav-drawer__item-label">{{ child.label }}</span>
                        <span class="app-nav-drawer__item-arrow" aria-hidden="true">›</span>
                      </button>
                    </div>
                  </template>
                </nav>

                <div class="app-nav-drawer__footer">
                  <p v-if="appVersion" class="app-nav-drawer__version">版本 v{{ appVersion }}</p>
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
