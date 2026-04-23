// frontend/src/components/report/charts/HeatmapBlock.tsx
import ReactECharts from 'echarts-for-react';
import { ChartFrame, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface HeatmapBlockProps {
  type: 'heatmap';
  title: string;
  x_labels: string[];
  y_labels: string[];
  values: number[][];
  options?: { height?: ChartHeight };
  forcedHeight?: ForcedHeight;
}

export function HeatmapBlock({ title, x_labels, y_labels, values, options, forcedHeight }: HeatmapBlockProps) {
  const points: [number, number, number][] = [];
  for (let y = 0; y < y_labels.length; y++) {
    for (let x = 0; x < x_labels.length; x++) {
      points.push([x, y, values[y]?.[x] ?? 0]);
    }
  }
  const all = points.map((p) => p[2]);
  const option = {
    tooltip: { position: 'top' },
    grid: { left: 60, right: 20, top: 30, bottom: 60 },
    xAxis: { type: 'category', data: x_labels, splitArea: { show: true } },
    yAxis: { type: 'category', data: y_labels, splitArea: { show: true } },
    visualMap: {
      min: Math.min(...all),
      max: Math.max(...all),
      calculable: true,
      orient: 'horizontal',
      bottom: 0,
    },
    series: [{ type: 'heatmap', data: points }],
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
