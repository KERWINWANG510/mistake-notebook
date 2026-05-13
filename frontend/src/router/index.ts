import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

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
      path: "/mistakes/new",
      name: "mistake-new",
      component: () => import("../views/MistakeNew.vue"),
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
      path: "/subjects",
      name: "subjects",
      component: () => import("../views/SubjectsView.vue"),
    },
    {
      path: "/grades",
      name: "grades",
      component: () => import("../views/GradesView.vue"),
    },
    {
      path: "/settings/ai",
      name: "settings-ai",
      component: () => import("../views/AiSettings.vue"),
    },
    {
      path: "/admin/users",
      name: "admin-users",
      component: () => import("../views/UsersAdmin.vue"),
      meta: { requiresAdmin: true },
    },
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

export default router;
