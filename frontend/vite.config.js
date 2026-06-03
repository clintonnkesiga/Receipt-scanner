import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5173,
    proxy: {
      // Forward API + uploaded images to the FastAPI backend.
      "/api": "http://localhost:8000",
      "/uploads": "http://localhost:8000",
    },
  },
});
