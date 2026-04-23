import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('echarts-for-react', () => ({
  default: ({ option }: { option: any }) => (
    <div data-testid="echart" data-option={JSON.stringify(option)} />
  ),
}));

import { LineChartBlock } from '../LineChartBlock';
import { BarChartBlock } from '../BarChartBlock';
import { AreaChartBlock } from '../AreaChartBlock';
import { PieChartBlock } from '../PieChartBlock';

describe('LineChartBlock', () => {
  it('renders the title and emits a line series', () => {
    render(
      <LineChartBlock
        type="line_chart"
        title="Gross Margin Trend"
        series={[{ name: 'Margin %', data: [{ x: 'Q1', y: 46.6 }, { x: 'Q2', y: 47.1 }] }]}
      />,
    );
    expect(screen.getByText('Gross Margin Trend')).toBeInTheDocument();
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option!);
    expect(opt.series[0].type).toBe('line');
    expect(opt.series[0].data).toEqual([46.6, 47.1]);
  });
});

describe('BarChartBlock', () => {
  it('emits a category x-axis and bar series', () => {
    render(
      <BarChartBlock
        type="bar_chart"
        title="Revenue by Segment"
        categories={['iPhone', 'Services']}
        series={[{ name: 'Q1 2026', values: [69.1, 26.3] }]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option!);
    expect(opt.xAxis.type).toBe('category');
    expect(opt.xAxis.data).toEqual(['iPhone', 'Services']);
    expect(opt.series[0].type).toBe('bar');
  });

  it('supports stacked vertical bars', () => {
    render(
      <BarChartBlock
        type="bar_chart"
        title="t"
        categories={['a']}
        series={[
          { name: 's1', values: [1] },
          { name: 's2', values: [2] },
        ]}
        stacked
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option!);
    expect(opt.series.every((s: any) => s.stack === 'total')).toBe(true);
  });
});

describe('AreaChartBlock', () => {
  it('emits a line series with areaStyle', () => {
    render(
      <AreaChartBlock
        type="area_chart"
        title="Revenue Composition"
        series={[{ name: 'iPhone', data: [{ x: 'Q1', y: 1 }] }]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option!);
    expect(opt.series[0].type).toBe('line');
    expect(opt.series[0].areaStyle).toBeDefined();
  });
});

describe('PieChartBlock', () => {
  it('emits a pie series with segment name/value pairs', () => {
    render(
      <PieChartBlock
        type="pie_chart"
        title="Revenue Mix"
        segments={[
          { label: 'iPhone', value: 69.1 },
          { label: 'Services', value: 26.3 },
        ]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option!);
    expect(opt.series[0].type).toBe('pie');
    expect(opt.series[0].data).toEqual([
      { name: 'iPhone', value: 69.1 },
      { name: 'Services', value: 26.3 },
    ]);
  });

  it('renders a donut when donut flag is set', () => {
    render(
      <PieChartBlock
        type="pie_chart"
        title="t"
        donut
        segments={[{ label: 'a', value: 1 }]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option!);
    expect(opt.series[0].radius[0]).not.toBe(0);
  });
});
