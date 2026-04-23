// frontend/src/components/report/charts/CandlestickBlock.tsx
import ReactECharts from 'echarts-for-react';
import { ChartFrame, CHART_PALETTE, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface CandleRow { date: string; open: number; high: number; low: number; close: number; }
export interface VolumeRow { date: string; value: number; }

export interface CandlestickBlockProps {
  type: 'candlestick_chart';
  title: string;
  data: CandleRow[];
  volume?: VolumeRow[];
  options?: { height?: ChartHeight };
  forcedHeight?: ForcedHeight;
}

export function CandlestickBlock({ title, data, volume, options, forcedHeight }: CandlestickBlockProps) {
  const categories = data.map((d) => d.date);
  const ohlc = data.map((d) => [d.open, d.close, d.low, d.high]);
  const series: any[] = [
    { type: 'candlestick', name: title, data: ohlc },
  ];
  if (volume && volume.length > 0) {
    series.push({ type: 'bar', name: 'Volume', yAxisIndex: 1, data: volume.map((v) => v.value) });
  }
  const option: any = {
    color: CHART_PALETTE,
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 40, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: categories },
    yAxis: [{ type: 'value' }, { type: 'value', show: Boolean(volume) }],
    series,
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
