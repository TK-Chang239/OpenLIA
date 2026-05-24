/* Shared helpers for hand-rolled SVG charts in the report renderer. Keeps
   axis ticks, label formatting, and color cycling consistent across every
   chart variant so the editorial aesthetic stays coherent. */

export const CHART_VIEWBOX = { W: 720, H: 220 };

export const CHART_PADDING = {
  L: 44,
  R: 16,
  T: 12,
  B: 28,
};

/** Compute pleasant axis ticks given a numeric range. */
export function niceTicks(min: number, max: number, count = 4): number[] {
  if (min === max) {
    if (min === 0) return [0, 1];
    const pad = Math.abs(min) * 0.1 || 1;
    return niceTicks(min - pad, min + pad, count);
  }
  const span = max - min;
  const step = Math.pow(10, Math.floor(Math.log10(span / count)));
  const err = (count * step) / span;
  let mult = 1;
  if (err <= 0.15) mult = 10;
  else if (err <= 0.35) mult = 5;
  else if (err <= 0.75) mult = 2;
  const niceStep = mult * step;
  let niceMin = Math.floor(min / niceStep) * niceStep;
  let niceMax = Math.ceil(max / niceStep) * niceStep;
  // Guarantee one step of headroom above the data so a bar whose value lands
  // exactly on a tick boundary (e.g., max=100 with niceStep=10) doesn't render
  // flush against the top of the plot area — visually that reads as the bar
  // exceeding the y-axis. Same idea below 0 when min is negative.
  if (max > 0 && niceMax <= max) niceMax += niceStep;
  if (min < 0 && niceMin >= min) niceMin -= niceStep;
  const ticks: number[] = [];
  for (let v = niceMin; v <= niceMax + niceStep / 2; v += niceStep) {
    ticks.push(Number(v.toFixed(8)));
  }
  return ticks;
}

/** Format a numeric axis tick with k/M/B/T suffix when appropriate. */
export function formatTick(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1_000_000_000_000) return `${(v / 1_000_000_000_000).toFixed(2)}T`;
  if (abs >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  if (abs >= 100) return v.toFixed(0);
  if (abs >= 10) return v.toFixed(1);
  if (abs > 0) return v.toFixed(2);
  return '0';
}

/** Map a Y value to an SVG y coordinate (top-down). */
export function yScale(y: number, yMin: number, yMax: number, t: number, b: number): number {
  if (yMax === yMin) return (t + b) / 2;
  return t + ((yMax - y) / (yMax - yMin)) * (b - t);
}

/** Pick a palette color, cycling at the end. */
export function paletteColor(idx: number): string {
  const i = ((idx % 8) + 8) % 8;
  return `var(--report-chart-${i + 1})`;
}

/** Build a list of nicely sampled x-axis labels — drops every other label
 *  when the category count is high to avoid tick collisions. */
export function visibleXLabels<T>(items: T[], maxLabels = 8): boolean[] {
  if (items.length <= maxLabels) return items.map(() => true);
  const step = Math.ceil(items.length / maxLabels);
  return items.map((_, i) => i % step === 0 || i === items.length - 1);
}
