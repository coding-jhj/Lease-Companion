import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  test: { exclude: ["e2e/**", "node_modules/**", "dist/**"] },
  plugins: [react()],
  server: {
    port: 5173,
    // Cloudflare Quick Tunnel 등으로 B PC 서버를 A·C가 원격 접속할 때 Host 헤더 허용
    allowedHosts: [".trycloudflare.com"],
    proxy: {
      "/api": {
        // 기본 8301. 로컬에서 포트 충돌 시 VITE_BACKEND_TARGET로 덮어쓴다.
        target: process.env.VITE_BACKEND_TARGET ?? "http://127.0.0.1:8301",
        changeOrigin: true,
      },
    },
  },
});
