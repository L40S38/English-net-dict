import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { sharedConfigPlugin } from "./vite-plugin-config";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), sharedConfigPlugin()],
});
