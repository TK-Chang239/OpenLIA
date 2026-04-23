// frontend/src/components/report/charts/WaterfallBlock.tsx
import ReactECharts from 'echarts-for-react';
import { ChartFrame, CHART_PALETTE, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

type ItemType = 'total' | 'increase' | 'decrease';

export interface WaterfallItem { label: string; value: number; type: ItemType; }

export interface WaterfallBlockProps {
  type: 'waterfall_chart';
  title: string;
  items: WaterfallItem[];
  options?: { height?: ChartHeight };
  forcedHeight?: ForcedHeight;
}

export function WaterfallBlock({ title, items, options, forcedHeight }: WaterfallBlockProps) {
  let running = 0;
  const placeholder: number[] = [];
  const increments: number[] = [];
  const decrements: number[] = [];
  const totals: number[] = [];
  for (const item of items) {
    if (item.type === 'total') {
      placeholder.push(0);
      totals.push(item.value);
      increments.push(0);
      decrements.push(0);
      running = item.value;
    } else if (item.type === 'increase') {
      placeholder.push(running);
      increments.push(item.value);
      decrements.push(0);
      totals.push(0);
      running += item.value;
    } else {
      running -= item.value;
      placeholder.push(running);
      increments.push(0);
      decrements.push(item.value);
      totals.push(0);
    }
  }
  const option = {
    color: CHART_PALETTE,
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: items.map((i) => i.label) },
    yAxis: { type: 'value' },
    series: [
      { type: 'bar', stack: 'wf', name: 'Placeholder', data: placeholder, itemStyle: { color: 'transparent' } },
      { type: 'bar', stack: 'wf', name: 'Increase', data: increments },
      { type: 'bar', stack: 'wf', name: 'Decrease', data: decrements },
      { type: 'bar', stack: 'wf', name: 'Total', data: totals },
    ],
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
