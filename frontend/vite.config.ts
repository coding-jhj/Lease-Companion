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
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
