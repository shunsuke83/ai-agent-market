import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Cloudflare Pages Functions live in web/functions and are picked up by wrangler
// from the project root (web/) at deploy time; Vite only builds the static SPA into dist/.
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE || "/",
  build: {
    outDir: "dist",
  },
  server: {
    port: 5173,
  },
});
