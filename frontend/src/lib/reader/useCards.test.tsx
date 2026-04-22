import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCards, CARDS_KEY } from "./useCards";

describe("useCards", () => {
  beforeEach(() => window.localStorage.clear());

  it("starts empty and persists new ask card to localStorage", () => {
    const { result } = renderHook(() => useCards("book-1"));
    expect(result.current.cards).toEqual([]);
    act(() => {
      result.current.createAsk({
        anchor: "p1.s1",
        quote: "hello",
        chapter: 1,
        question: "what?",
      });
    });
    expect(result.current.cards).toHaveLength(1);
    const raw = window.localStorage.getItem(CARDS_KEY("book-1"));
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!);
    expect(parsed.version).toBe(1);
    expect(parsed.cards[0].kind).toBe("ask");
    expect(parsed.cards[0].quote).toBe("hello");
  });

  it("updateAsk mutates answer field and persists", () => {
    const { result } = renderHook(() => useCards("book-1"));
    let id = "";
    act(() => {
      id = result.current.createAsk({
        anchor: "p1.s1",
        quote: "q",
        chapter: 1,
        question: "Q?",
      });
    });
    act(() => {
      result.current.updateAsk(id, (prev) => ({ ...prev, answer: "A" }));
    });
    const card = result.current.cards.find((c) => c.id === id);
    expect(card && card.kind === "ask" && card.answer).toBe("A");
  });

  it("createNote with empty body is allowed (body committed later)", () => {
    const { result } = renderHook(() => useCards("book-1"));
    act(() => {
      result.current.createNote({ anchor: "p1.s2", quote: "x", chapter: 1 });
    });
    expect(result.current.cards[0].kind).toBe("note");
  });

  it("removeCard deletes by id and persists", () => {
    const { result } = renderHook(() => useCards("book-1"));
    let id = "";
    act(() => {
      id = result.current.createNote({ anchor: "p1.s1", quote: "x", chapter: 1 });
    });
    act(() => result.current.removeCard(id));
    expect(result.current.cards).toEqual([]);
  });

  it("restores from localStorage on mount", () => {
    window.localStorage.setItem(
      CARDS_KEY("book-1"),
      JSON.stringify({
        version: 1,
        cards: [
          {
            id: "abc",
            bookId: "book-1",
            anchor: "p1.s1",
            quote: "q",
            chapter: 1,
            kind: "note",
            body: "hi",
            createdAt: "2026-04-22T00:00:00Z",
            updatedAt: "2026-04-22T00:00:00Z",
          },
        ],
      }),
    );
    const { result } = renderHook(() => useCards("book-1"));
    expect(result.current.cards).toHaveLength(1);
    expect(result.current.cards[0].id).toBe("abc");
  });

  it("isolates cards per bookId", () => {
    const { result: a } = renderHook(() => useCards("a"));
    act(() => a.current.createNote({ anchor: "p1.s1", quote: "x", chapter: 1 }));
    const { result: b } = renderHook(() => useCards("b"));
    expect(b.current.cards).toEqual([]);
  });

  it("appendFollowup pushes a followup entry to an ask card", () => {
    const { result } = renderHook(() => useCards("book-1"));
    let id = "";
    act(() => {
      id = result.current.createAsk({
        anchor: "p1.s1",
        quote: "q",
        chapter: 1,
        question: "Q?",
      });
    });
    act(() => {
      result.current.appendFollowup(id, "why?", "");
    });
    const card = result.current.cards.find((c) => c.id === id);
    expect(card && card.kind === "ask" && card.followups).toHaveLength(1);
    expect(
      card && card.kind === "ask" && card.followups[0],
    ).toEqual({ question: "why?", answer: "" });
  });

  it("appendFollowup then updateAsk can stream into the latest followup answer", () => {
    const { result } = renderHook(() => useCards("book-1"));
    let id = "";
    act(() => {
      id = result.current.createAsk({
        anchor: "p1.s1",
        quote: "q",
        chapter: 1,
        question: "Q?",
      });
    });
    act(() => {
      result.current.appendFollowup(id, "why?", "");
    });
    act(() => {
      result.current.updateAsk(id, (prev) => ({
        ...prev,
        followups: prev.followups.map((f, i, arr) =>
          i === arr.length - 1 ? { ...f, answer: "streamed" } : f,
        ),
      }));
    });
    const card = result.current.cards.find((c) => c.id === id);
    expect(card && card.kind === "ask" && card.followups.length).toBe(1);
    expect(
      card && card.kind === "ask" && card.followups[0].answer,
    ).toBe("streamed");
  });

  it("setAskLoading flips card.loading in memory but is stripped on persist", () => {
    const { result } = renderHook(() => useCards("book-1"));
    let id = "";
    act(() => {
      id = result.current.createAsk({
        anchor: "p1.s1",
        quote: "q",
        chapter: 1,
        question: "Q?",
      });
    });
    act(() => {
      result.current.setAskLoading(id, true);
    });
    const mem = result.current.cards.find((c) => c.id === id) as
      | (import("./cards").AskCard & { loading?: boolean })
      | undefined;
    expect(mem?.loading).toBe(true);
    const raw = window.localStorage.getItem(CARDS_KEY("book-1"))!;
    const parsed = JSON.parse(raw);
    expect(parsed.cards[0].loading).toBeUndefined();
  });

  it("setAskStreaming flips card.streaming in memory but is stripped on persist", () => {
    const { result } = renderHook(() => useCards("book-1"));
    let id = "";
    act(() => {
      id = result.current.createAsk({
        anchor: "p1.s1",
        quote: "q",
        chapter: 1,
        question: "Q?",
      });
    });
    act(() => {
      result.current.setAskStreaming(id, true);
    });
    const mem = result.current.cards.find((c) => c.id === id) as
      | (import("./cards").AskCard & { streaming?: boolean })
      | undefined;
    expect(mem?.streaming).toBe(true);
    const parsed = JSON.parse(
      window.localStorage.getItem(CARDS_KEY("book-1"))!,
    );
    expect(parsed.cards[0].streaming).toBeUndefined();
  });
});
