/// <reference types="vite/client" />

declare module "*.svg" {
  const src: string;
  export default src;
}

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_APP_VERSION?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
