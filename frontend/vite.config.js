import {
  sveltekit
} from "@sveltejs/kit/vite";
import {
  defineConfig
} from "vite";

// In Docker the backend is reachable at http://backend:8000.
// Locally it stays at http://localhost:8000.
const apiUrl = process.env.API_URL ? ? "http://localhost:8000";

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    host: true, // bind to 0.0.0.0 so the container port is reachable
    port: 5173,
    proxy: {
      // Forward API + uploaded images to the FastAPI backend.
      "/api": apiUrl,
      "/uploads": apiUrl,
    },
  },
});