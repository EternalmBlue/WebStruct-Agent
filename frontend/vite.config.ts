import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";

function readApiTarget() {
  const configPath = path.resolve(__dirname, "../config.toml");
  try {
    const text = fs.readFileSync(configPath, "utf8");
    const frontend = text.match(/\[frontend\]([\s\S]*?)(?=\n\[|$)/)?.[1] ?? "";
    return frontend.match(/api_target\s*=\s*"([^"]+)"/)?.[1] ?? "http://127.0.0.1:8000";
  } catch {
    return "http://127.0.0.1:8000";
  }
}

const apiTarget = readApiTarget();

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true
      }
    }
  }
});
