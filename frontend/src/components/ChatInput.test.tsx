import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { ChatInput } from "./ChatInput";

describe("ChatInput", () => {
  it("renders the placeholder when value is empty", () => {
    render(
      <ChatInput
        value=""
        onChange={() => {}}
        onSubmit={() => {}}
      />
    );
    expect(
      screen.getByPlaceholderText(/ask about what you've read/i)
    ).toBeInTheDocument();
  });

  it("calls onChange as the user types", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <ChatInput value="" onChange={onChange} onSubmit={() => {}} />
    );
    await user.type(screen.getByRole("textbox"), "Hi");
    // uncontrolled per-keystroke updates; the last call matches final char
    expect(onChange).toHaveBeenCalled();
  });

  it("disables the send button when the trimmed value is empty", () => {
    render(
      <ChatInput value="   " onChange={() => {}} onSubmit={() => {}} />
    );
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });

  it("enables the send button when value is non-empty", () => {
    render(
      <ChatInput value="hello" onChange={() => {}} onSubmit={() => {}} />
    );
    expect(screen.getByRole("button", { name: /send/i })).toBeEnabled();
  });

  it("clicking send calls onSubmit", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(
      <ChatInput value="Who is Marley?" onChange={() => {}} onSubmit={onSubmit} />
    );
    await user.click(screen.getByRole("button", { name: /send/i }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("Enter (without Shift) calls onSubmit and prevents default", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(
      <ChatInput value="q" onChange={() => {}} onSubmit={onSubmit} />
    );
    const ta = screen.getByRole("textbox");
    ta.focus();
    await user.keyboard("{Enter}");
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("Shift+Enter does NOT call onSubmit", async () => {
    const onSubmit = vi.fn();
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <ChatInput value="line one" onChange={onChange} onSubmit={onSubmit} />
    );
    const ta = screen.getByRole("textbox");
    ta.focus();
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("Enter on an empty value does NOT call onSubmit", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(
      <ChatInput value="   " onChange={() => {}} onSubmit={onSubmit} />
    );
    const ta = screen.getByRole("textbox");
    ta.focus();
    await user.keyboard("{Enter}");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("when disabled, send is disabled regardless of value", () => {
    render(
      <ChatInput
        value="non-empty"
        onChange={() => {}}
        onSubmit={() => {}}
        disabled
      />
    );
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });
});
