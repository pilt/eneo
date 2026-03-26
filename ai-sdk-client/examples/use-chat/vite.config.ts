import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The eneo backend URL — override via VITE_ENEO_URL env var.
const ENEO_URL = process.env.VITE_ENEO_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy /api to the eneo backend so the browser avoids CORS issues
      // during local development.
      "/api": {
        target: ENEO_URL,
        changeOrigin: true,
      },
    },
  },
});
