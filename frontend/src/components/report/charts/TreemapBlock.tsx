// frontend/src/components/report/charts/TreemapBlock.tsx
import ReactECharts from 'echarts-for-react';
import { ChartFrame, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface TreemapNode { name: string; value: number; children?: TreemapNode[]; }

export interface TreemapBlockProps {
  type: 'treemap';
  title: string;
  data: TreemapNode[];
  options?: { height?: ChartHeight };
  forcedHeight?: ForcedHeight;
}

export function TreemapBlock({ title, data, options, forcedHeight }: TreemapBlockProps) {
  const option = {
    tooltip: { trigger: 'item' },
    series: [{ type: 'treemap', data }],
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
