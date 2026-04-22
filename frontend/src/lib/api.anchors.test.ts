import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fetchChapter, type Chapter } from "./api";

const BOOK = "carol";
const URL = "http://localhost:8000/books/carol/chapters/1";

describe("fetchChapter — anchored paragraphs", () => {
  const realFetch = global.fetch;
  beforeEach(() => {
    global.fetch = vi.fn(async () =>
      new Response(
        JSON.stringify({
          num: 1,
          title: "Marley's Ghost",
          paragraphs: ["Marley was dead. No doubt."],
          paragraphs_anchored: [
            {
              paragraph_idx: 1,
              sentences: [
                { sid: "p1.s1", text: "Marley was dead." },
                { sid: "p1.s2", text: "No doubt." },
              ],
            },
          ],
          anchors_fallback: false,
          has_prev: false,
          has_next: false,
          total_chapters: 1,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as typeof fetch;
  });
  afterEach(() => {
    global.fetch = realFetch;
  });

  it("parses paragraphs_anchored + anchors_fallback", async () => {
    const ch: Chapter = await fetchChapter(BOOK, 1);
    expect(ch.anchors_fallback).toBe(false);
    expect(ch.paragraphs_anchored).toHaveLength(1);
    const p1 = ch.paragraphs_anchored[0];
    expect(p1.paragraph_idx).toBe(1);
    expect(p1.sentences.map((s) => s.sid)).toEqual(["p1.s1", "p1.s2"]);
    expect(p1.sentences[0].text).toBe("Marley was dead.");
    void URL;
  });
});
