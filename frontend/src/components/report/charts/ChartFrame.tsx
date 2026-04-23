import type { ReactNode } from 'react';
import type { ForcedHeight } from '../blocks/GroupBlock';

export type ChartHeight = 'small' | 'medium' | 'tall';

export const CHART_HEIGHT_PX: Record<ChartHeight, number> = {
  small: 200,
  medium: 300,
  tall: 400,
};

export const CHART_PALETTE = [
  'var(--report-chart-1)',
  'var(--report-chart-2)',
  'var(--report-chart-3)',
  'var(--report-chart-4)',
  'var(--report-chart-5)',
  'var(--report-chart-6)',
  'var(--report-chart-7)',
  'var(--report-chart-8)',
];

export interface ChartFrameProps {
  title: string;
  height?: ChartHeight;
  forcedHeight?: ForcedHeight;
  children: ReactNode;
}

export function resolveHeight(
  declared?: ChartHeight,
  forced?: ForcedHeight,
): number {
  const key = (forced ?? declared ?? 'medium') as ChartHeight;
  return CHART_HEIGHT_PX[key] ?? CHART_HEIGHT_PX.medium;
}

export function ChartFrame({ title, height, forcedHeight, children }: ChartFrameProps) {
  const px = resolveHeight(height, forcedHeight);
  return (
    <figure className="report-chart">
      <figcaption className="report-chart__title">{title}</figcaption>
      <div style={{ height: px }}>{children}</div>
    </figure>
  );
}
