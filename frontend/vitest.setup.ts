import "@testing-library/jest-dom/vitest";

// RTL's waitFor uses `jestFakeTimersAreEnabled()` which checks for `typeof jest`.
// Vitest 2 does not inject `jest` as a global by default; expose vi as jest so
// the fake-timer code path in waitFor works correctly with vi.useFakeTimers().
// @ts-expect-error — intentional global injection
globalThis.jest = vi;
