import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import Components from "unplugin-vue-components/vite";
import { NaiveUiResolver } from "unplugin-vue-components/resolvers";

export default defineConfig({
  plugins: [
    vue(),
    Components({
      resolvers: [NaiveUiResolver()],
      dts: true,
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/naive-ui")) return "naive-ui";
          if (id.includes("node_modules/vue/")) return "vue-core";
          if (id.includes("node_modules/vue-router")) return "vue-router";
          if (id.includes("node_modules/pinia")) return "pinia";
          if (id.includes("node_modules/axios")) return "axios";
        },
      },
    },
  },
});
