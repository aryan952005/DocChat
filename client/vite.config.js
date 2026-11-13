import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Port 5173 is often taken by another Vite project, so DocChat uses 5174 and fails loudly if it is busy
export default defineConfig({
  plugins: [react()],
  server: { port: 5174, strictPort: true },
});
