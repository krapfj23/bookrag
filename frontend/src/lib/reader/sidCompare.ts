export function parseSid(sid: string): [number, number] {
  const m = /^p(\d+)\.s(\d+)$/.exec(sid);
  if (!m) return [0, 0];
  return [Number.parseInt(m[1], 10), Number.parseInt(m[2], 10)];
}

export function compareSid(a: string, b: string): number {
  const [pa, sa] = parseSid(a);
  const [pb, sb] = parseSid(b);
  if (pa !== pb) return pa - pb;
  return sa - sb;
}
