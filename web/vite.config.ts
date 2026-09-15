import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { workspaceMockPlugin } from "./src/workspace/mock/plugin";

export default defineConfig({
  plugins: [react(), workspaceMockPlugin()],
  server: { strictPort: true, port: 5173 },
  preview: { strictPort: true, port: 4173 },
});
