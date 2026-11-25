import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  // Reads .env files and the shell environment ("" = no prefix filter).
  const env = loadEnv(mode, ".", "");
  // In development, /api is proxied to FastAPI so the browser talks to a
  // single origin. Override the target with OPENCAMPUS_API_URL if needed.
  const apiTarget = env.OPENCAMPUS_API_URL || "http://127.0.0.1:8000";

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: {
        "/api": { target: apiTarget, changeOrigin: true },
      },
    },
  };
});
