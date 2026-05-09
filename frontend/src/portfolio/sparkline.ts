/** Deterministic per-ticker sparkline generator.
 *  Returns 9 points (suitable for a 64x22 viewBox) and a sign.
 *  Same input always yields the same output, so squiggles don't flicker
 *  between renders. Backed by a simple FNV-ish hash of the ticker. */

export type SparkSign = "up" | "flat" | "down";

export interface Sparkline {
  points: number[]; // y in [2, 20] for a 22h viewBox
  sign: SparkSign;
}

function hashSeed(input: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = (h * 16777619) >>> 0;
  }
  return h >>> 0;
}

function lcg(seed: number): () => number {
  let s = seed || 1;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return (s & 0xffff) / 0xffff;
  };
}

export function sparkFor(
  ticker: string,
  count: number = 9,
): Sparkline {
  const rand = lcg(hashSeed(ticker.toUpperCase()));
  const drift = (rand() - 0.5) * 12; // overall trend in y units
  const start = 8 + rand() * 8; // y starts in [8, 16]
  const points: number[] = [];
  let y = start;
  for (let i = 0; i < count; i++) {
    const noise = (rand() - 0.5) * 4;
    const trend = (drift / (count - 1)) * 1;
    y = Math.max(2, Math.min(20, y + trend + noise));
    points.push(Math.round(y * 10) / 10);
  }
  const delta = points[points.length - 1] - points[0];
  const sign: SparkSign = delta < -1.5 ? "down" : delta > 1.5 ? "up" : "flat";
  return { points, sign };
}

/** SVG path string for a polyline through the given points across viewBox width. */
export function sparkPath(
  points: number[],
  width: number = 64,
): string {
  if (points.length === 0) return "";
  const step = width / (points.length - 1);
  return points
    .map((y, i) => `${i === 0 ? "M" : "L"}${(i * step).toFixed(2)},${y.toFixed(1)}`)
    .join(" ");
}
