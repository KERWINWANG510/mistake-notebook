import axios from "axios";

export const apiBase = import.meta.env.VITE_API_BASE ?? "";

const TOKEN_KEY = "mn_access_token";

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export const http = axios.create({
  baseURL: apiBase,
  timeout: 180000,
});

http.interceptors.request.use((config) => {
  const t = getStoredToken();
  if (t) {
    config.headers.Authorization = `Bearer ${t}`;
  }
  return config;
});

function mapClientErrorMessage(raw: string | undefined): string {
  if (!raw) return "请求失败";
  const t = raw.trim();
  if (t === "Network Error") return "网络异常，请检查网络连接或服务地址是否正确";
  if (/timeout/i.test(t) || t.includes("ECONNABORTED")) return "请求超时，请稍后重试";
  if (t === "Request failed with status code 401") return "未登录或登录已过期，请重新登录";
  if (t === "Request failed with status code 403") return "没有权限执行此操作";
  if (t === "Request failed with status code 404") return "请求的资源不存在";
  if (t.startsWith("Request failed with status code ")) {
    const code = t.slice("Request failed with status code ".length);
    return `请求失败（HTTP ${code}）`;
  }
  return t;
}

http.interceptors.response.use(
  (r) => r,
  (err) => {
    const d = err.response?.data?.detail;
    let msg: string;
    if (Array.isArray(d)) {
      msg = d.map((x: { msg?: string }) => x.msg ?? JSON.stringify(x)).join("；");
    } else if (typeof d === "string") {
      msg = d;
    } else if (d && typeof d === "object" && "message" in d) {
      msg = String((d as { message: unknown }).message);
    } else {
      msg = mapClientErrorMessage(err.message);
    }
    return Promise.reject(new Error(msg));
  },
);
