import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const ENEO_URL = env.VITE_ENEO_URL ?? "http://localhost:8000";

  return {
  plugins: [react()],
  server: {
    allowedHosts: true,
    proxy: {
      // Proxy /api to the eneo backend so the browser avoids CORS issues
      // during local development.
      "/api": {
        target: ENEO_URL,
        changeOrigin: true,
        // eneo mounts its API at /api/v1 — rewrite /api/* → /api/v1/*
        rewrite: (path) => path.replace(/^\/api/, "/api/v1"),
      },
    },
  },
};
});
