export interface StreamOptions {
  onChunk: (soFar: string) => void;
  minMs?: number;
  maxMs?: number;
  minWords?: number;
  maxWords?: number;
  signal?: AbortSignal;
}

export async function simulateStream(
  full: string,
  opts: StreamOptions,
): Promise<void> {
  const {
    onChunk,
    minMs = 25,
    maxMs = 60,
    minWords = 1,
    maxWords = 3,
    signal,
  } = opts;
  if (!full) {
    onChunk("");
    return;
  }
  // Preserve whitespace by splitting on word-boundaries while keeping separators.
  const tokens = full.match(/\S+\s*/g) ?? [full];
  let idx = 0;
  let soFar = "";
  while (idx < tokens.length) {
    if (signal?.aborted) return;
    const take =
      minWords +
      Math.floor(Math.random() * Math.max(1, maxWords - minWords + 1));
    const slice = tokens.slice(idx, idx + take).join("");
    soFar += slice;
    idx += take;
    onChunk(soFar);
    if (idx >= tokens.length) break;
    const delay =
      minMs + Math.floor(Math.random() * Math.max(1, maxMs - minMs + 1));
    await new Promise<void>((resolve) => {
      const t = setTimeout(resolve, delay);
      signal?.addEventListener("abort", () => {
        clearTimeout(t);
        resolve();
      });
    });
  }
}
