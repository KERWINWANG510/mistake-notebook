import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { http, getStoredToken, setStoredToken } from "../api/http";
import type { MeUser } from "../api/client";

export const useAuthStore = defineStore("auth", () => {
  const token = ref(getStoredToken() ?? "");
  const me = ref<MeUser | null>(null);

  const isLoggedIn = computed(() => Boolean(token.value));

  async function login(username: string, password: string) {
    const { data } = await http.post<{ access_token: string; token_type: string; user: MeUser }>("/api/auth/login", {
      username,
      password,
    });
    token.value = data.access_token;
    setStoredToken(data.access_token);
    me.value = data.user;
  }

  function logout() {
    token.value = "";
    me.value = null;
    setStoredToken(null);
  }

  async function fetchMe() {
    if (!token.value) {
      me.value = null;
      return;
    }
    try {
      const { data } = await http.get<MeUser>("/api/auth/me");
      me.value = data;
    } catch {
      logout();
    }
  }

  return { token, me, isLoggedIn, login, logout, fetchMe };
});
