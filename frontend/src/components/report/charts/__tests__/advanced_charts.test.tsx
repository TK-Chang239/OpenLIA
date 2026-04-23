import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('echarts-for-react', () => ({
  default: ({ option }: { option: any }) => (
    <div data-testid="echart" data-option={JSON.stringify(option)} />
  ),
}));

import { CandlestickBlock } from '../CandlestickBlock';
import { WaterfallBlock } from '../WaterfallBlock';
import { ScatterBlock } from '../ScatterBlock';
import { HeatmapBlock } from '../HeatmapBlock';
import { TreemapBlock } from '../TreemapBlock';
import { ComboChartBlock } from '../ComboChartBlock';

describe('CandlestickBlock', () => {
  it('emits candlestick series with OHLC data', () => {
    render(
      <CandlestickBlock
        type="candlestick_chart"
        title="AAPL"
        data={[
          { date: '2026-04-01', open: 1, high: 2, low: 0.5, close: 1.8 },
        ]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option!);
    const cs = opt.series.find((s: any) => s.type === 'candlestick');
    expect(cs.data[0]).toEqual([1, 1.8, 0.5, 2]);
  });

  it('adds a volume bar series when volume is provided', () => {
    render(
      <CandlestickBlock
        type="candlestick_chart"
        title="AAPL"
        data={[{ date: 'd1', open: 1, high: 2, low: 0, close: 1 }]}
        volume={[{ date: 'd1', value: 100 }]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option!);
    expect(opt.series.some((s: any) => s.type === 'bar' && s.name === 'Volume')).toBe(true);
  });
});

describe('WaterfallBlock', () => {
  it('emits bar series with totals and increments', () => {
    render(
      <WaterfallBlock
        type="waterfall_chart"
        title="Revenue Bridge"
        items={[
          { label: 'Start', value: 10, type: 'total' },
          { label: 'A', value: 2, type: 'increase' },
          { label: 'End', value: 12, type: 'total' },
        ]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option!);
    expect(opt.xAxis.data).toEqual(['Start', 'A', 'End']);
  });
});

describe('ScatterBlock', () => {
  it('emits a scatter series', () => {
    render(
      <ScatterBlock
        type="scatter_plot"
        title="P/E vs Growth"
        series={[{ name: 'Peers', data: [{ x: 15.2, y: 32.1 }, { x: 22.4, y: 28.7 }] }]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option!);
    expect(opt.series[0].type).toBe('scatter');
    expect(opt.series[0].data[0]).toEqual([15.2, 32.1]);
  });
});

describe('HeatmapBlock', () => {
  it('emits a heatmap series with [x,y,value] points', () => {
    render(
      <HeatmapBlock
        type="heatmap"
        title="Correlation"
        x_labels={['A', 'B']}
        y_labels={['A', 'B']}
        values={[
          [1.0, 0.82],
          [0.82, 1.0],
        ]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option!);
    expect(opt.series[0].type).toBe('heatmap');
    expect(opt.series[0].data).toHaveLength(4);
  });
});

describe('TreemapBlock', () => {
  it('emits a treemap series with nested children', () => {
    render(
      <TreemapBlock
        type="treemap"
        title="Revenue by Segment"
        data={[{ name: 'iPhone', value: 69.1, children: [{ name: '16', value: 42.0 }] }]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option!);
    expect(opt.series[0].type).toBe('treemap');
    expect(opt.series[0].data[0].children[0].name).toBe('16');
  });
});

describe('ComboChartBlock', () => {
  it('emits a bar + line series pair with two y-axes', () => {
    render(
      <ComboChartBlock
        type="combo_chart"
        title="Rev & Margin"
        categories={['Q1', 'Q2']}
        bar_series={[{ name: 'Rev', values: [1, 2] }]}
        line_series={[{ name: 'Margin', values: [10, 11] }]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option!);
    expect(Array.isArray(opt.yAxis)).toBe(true);
    expect(opt.yAxis).toHaveLength(2);
    const types = opt.series.map((s: any) => s.type);
    expect(types).toContain('bar');
    expect(types).toContain('line');
  });
});
