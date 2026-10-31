import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Dev proxy: backend runs on :8000 (uvicorn app.main:app)
    proxy: { "/api": "http://localhost:8000" },
  },
});
