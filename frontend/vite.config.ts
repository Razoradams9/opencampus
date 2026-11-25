import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

/** The slice of Vite's proxy event API used below (avoids pulling in @types/node). */
interface ProxyRequestEvents {
  on(event: "proxyReq", listener: (proxyReq: { removeHeader(name: string): void }) => void): void;
}

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
        "/api": {
          target: apiTarget,
          changeOrigin: true,
          // Never forward client-supplied forwarding headers: the API (and
          // uvicorn, which trusts them from 127.0.0.1 by default) would
          // otherwise let a browser choose its own rate-limit identity.
          configure: (proxy) => {
            (proxy as unknown as ProxyRequestEvents).on("proxyReq", (proxyReq) => {
              for (const header of ["x-forwarded-for", "x-real-ip", "forwarded"]) proxyReq.removeHeader(header);
            });
          },
        },
      },
    },
  };
});
