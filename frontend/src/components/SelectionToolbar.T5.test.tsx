/**
 * T5 — SelectionToolbar enter animation class.
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { SelectionToolbar } from "./SelectionToolbar";

describe("SelectionToolbar T5 — enter animation", () => {
  it("root element has rr-toolbar-enter class", () => {
    const { getByRole } = render(
      <SelectionToolbar top={100} left={200} onAction={() => {}} />
    );
    const toolbar = getByRole("toolbar");
    expect(toolbar.className).toContain("rr-toolbar-enter");
  });
});
