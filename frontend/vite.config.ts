import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Tell esbuild to parse JSX in .ts files (needed for pageSide.test.ts).
  esbuild: {
    jsx: "automatic",
    jsxImportSource: "react",
    include: /\.tsx?$/,
    exclude: [],
    loader: "tsx",
  },
  server: { port: 5173, strictPort: true },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    css: false,
    exclude: ["**/node_modules/**", "**/dist/**", "e2e/**"],
    // Isolate each test file in its own worker. Several tests mock
    // module-level exports (vi.spyOn(api, ...)) and globalThis.fetch;
    // without isolation those spies leak between files under parallelism.
    isolate: true,
    fileParallelism: false,
  },
});
