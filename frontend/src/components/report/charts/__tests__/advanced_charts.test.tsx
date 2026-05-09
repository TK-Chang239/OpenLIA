import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { CandlestickBlock } from '../CandlestickBlock';
import { WaterfallBlock } from '../WaterfallBlock';
import { ScatterBlock } from '../ScatterBlock';
import { HeatmapBlock } from '../HeatmapBlock';
import { TreemapBlock } from '../TreemapBlock';
import { ComboChartBlock } from '../ComboChartBlock';

describe('CandlestickBlock', () => {
  it('renders one body rect + wick line per candle', () => {
    const { container } = render(
      <CandlestickBlock
        type="candlestick_chart"
        title="AAPL"
        data={[
          { date: '2026-04-01', open: 1, high: 2, low: 0.5, close: 1.8 },
          { date: '2026-04-02', open: 1.8, high: 2.2, low: 1.4, close: 1.5 },
        ]}
      />,
    );
    expect(container.querySelectorAll('svg rect')).toHaveLength(2);
    const wicks = container.querySelectorAll('svg line');
    expect(wicks.length).toBeGreaterThanOrEqual(2);
  });

  it('renders volume bars when volume is provided', () => {
    const { container } = render(
      <CandlestickBlock
        type="candlestick_chart"
        title="AAPL"
        data={[{ date: 'd1', open: 1, high: 2, low: 0, close: 1 }]}
        volume={[{ date: 'd1', value: 100 }]}
      />,
    );
    expect(container.querySelectorAll('svg rect').length).toBeGreaterThanOrEqual(2);
  });
});

describe('WaterfallBlock', () => {
  it('renders one bar per item with x-axis labels', () => {
    const { container } = render(
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
    expect(container.querySelectorAll('svg rect')).toHaveLength(3);
    expect(screen.getByText('Start')).toBeInTheDocument();
    expect(screen.getByText('End')).toBeInTheDocument();
  });
});

describe('ScatterBlock', () => {
  it('renders one circle per data point', () => {
    const { container } = render(
      <ScatterBlock
        type="scatter_plot"
        title="P/E vs Growth"
        series={[{ name: 'Peers', data: [{ x: 15.2, y: 32.1 }, { x: 22.4, y: 28.7 }] }]}
      />,
    );
    expect(container.querySelectorAll('svg circle')).toHaveLength(2);
  });
});

describe('HeatmapBlock', () => {
  it('renders one cell per (x, y)', () => {
    const { container } = render(
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
    expect(container.querySelectorAll('svg rect')).toHaveLength(4);
  });
});

describe('TreemapBlock', () => {
  it('renders nested rects when children are present', () => {
    const { container } = render(
      <TreemapBlock
        type="treemap"
        title="Revenue by Segment"
        data={[
          { name: 'iPhone', value: 69.1, children: [{ name: '16', value: 42.0 }] },
          { name: 'Services', value: 26.3 },
        ]}
      />,
    );
    expect(container.querySelectorAll('svg rect').length).toBeGreaterThanOrEqual(3);
  });
});

describe('ComboChartBlock', () => {
  it('renders bar rects and a line polyline together', () => {
    const { container } = render(
      <ComboChartBlock
        type="combo_chart"
        title="Rev & Margin"
        categories={['Q1', 'Q2']}
        bar_series={[{ name: 'Rev', values: [1, 2] }]}
        line_series={[{ name: 'Margin', values: [10, 11] }]}
      />,
    );
    expect(container.querySelectorAll('svg rect').length).toBeGreaterThanOrEqual(2);
    expect(container.querySelectorAll('svg polyline.series-line')).toHaveLength(1);
  });
});
