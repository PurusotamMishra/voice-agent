import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: the API runs on :8000 (`uv run python -m voice_agent.api`); in Docker nginx proxies /api.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});
