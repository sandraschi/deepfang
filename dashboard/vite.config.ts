import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 10957,
    strictPort: true,
    proxy: {
      "/api": "http://localhost:10956",
      "/health": "http://localhost:10956",
      "/sse": "http://localhost:10956",
    },
  },
});
