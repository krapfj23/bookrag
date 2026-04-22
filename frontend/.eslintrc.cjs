module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: {
    project: "./tsconfig.eslint.json",
    ecmaVersion: 2022,
    sourceType: "module",
  },
  plugins: ["@typescript-eslint", "react", "react-hooks"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react/jsx-runtime",
    "plugin:react-hooks/recommended",
  ],
  settings: { react: { version: "detect" } },
  rules: {
    "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    "@typescript-eslint/no-explicit-any": "error",
    "react/no-unescaped-entities": "off",
    // Legitimate initialization/synchronization patterns (loading state,
    // mode-switch reset) legitimately call setState inside effects.
    "react-hooks/set-state-in-effect": "off",
  },
  ignorePatterns: ["dist/", "node_modules/", "e2e/", "*.cjs", "vite.config.*", "vitest.setup.ts"],
};
