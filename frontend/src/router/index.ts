import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { scheduleSearchScrollRestore } from "../utils/searchScrollRestore";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("../views/Login.vue"),
      meta: { public: true },
    },
    { path: "/", redirect: "/mistakes" },
    {
      path: "/mistakes",
      name: "mistakes",
      component: () => import("../views/MistakeList.vue"),
    },
    {
      path: "/search",
      name: "mistake-search",
      component: () => import("../views/MistakeSearchView.vue"),
      meta: { keepAlive: true },
    },
    {
      path: "/mistakes/new",
      name: "mistake-new",
      component: () => import("../views/MistakeNew.vue"),
    },
    {
      path: "/mistakes/:id/practice",
      name: "mistake-practice",
      component: () => import("../views/MistakePractice.vue"),
    },
    {
      path: "/mistakes/:id/edit",
      name: "mistake-edit",
      component: () => import("../views/MistakeEdit.vue"),
    },
    {
      path: "/mistakes/:id",
      name: "mistake-detail",
      component: () => import("../views/MistakeDetail.vue"),
    },
    {
      path: "/stats",
      name: "statistics",
      component: () => import("../views/StatisticsView.vue"),
    },
    {
      path: "/review",
      name: "review-today",
      component: () => import("../views/ReviewTodayView.vue"),
    },
    {
      path: "/practice/mock-paper",
      name: "mock-paper",
      component: () => import("../views/MockPaperView.vue"),
    },
    {
      path: "/grade-subjects",
      name: "grade-subjects",
      component: () => import("../views/GradeSubjectsView.vue"),
    },
    { path: "/subjects", redirect: "/grade-subjects" },
    { path: "/grades", redirect: "/grade-subjects" },
    { path: "/practice", redirect: "/practice/mock-paper" },
    {
      path: "/settings",
      component: () => import("../views/SystemSettingsLayout.vue"),
      redirect: "/settings/general",
      children: [
        {
          path: "general",
          name: "settings-general",
          component: () => import("../views/GeneralSettings.vue"),
        },
        {
          path: "ai",
          name: "settings-ai",
          component: () => import("../views/AiSettings.vue"),
        },
        {
          path: "users",
          name: "settings-users",
          component: () => import("../views/UsersAdmin.vue"),
          meta: { requiresAdmin: true },
        },
      ],
    },
    { path: "/admin/users", redirect: "/settings/users" },
    { path: "/settings/user", redirect: "/settings/users" },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (to.meta.public) {
    if (to.path === "/login" && auth.token) {
      await auth.fetchMe();
      if (auth.me) {
        const r = typeof to.query.redirect === "string" ? to.query.redirect : "";
        return r || "/mistakes";
      }
    }
    return true;
  }
  if (!auth.token) {
    return { path: "/login", query: { redirect: to.fullPath } };
  }
  if (!auth.me) {
    await auth.fetchMe();
  }
  if (!auth.me) {
    return { path: "/login", query: { redirect: to.fullPath } };
  }
  if (to.meta.requiresAdmin && !auth.me.is_admin) {
    return { path: "/mistakes" };
  }
  return true;
});

router.afterEach((to, from) => {
  if (to.path.startsWith("/search") && /^\/mistakes\/[^/]+$/.test(from.path)) {
    scheduleSearchScrollRestore();
  }
});

export default router;
