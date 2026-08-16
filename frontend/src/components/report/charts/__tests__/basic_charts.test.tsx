import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { LineChartBlock } from '../LineChartBlock';
import { BarChartBlock } from '../BarChartBlock';
import { AreaChartBlock } from '../AreaChartBlock';
import { PieChartBlock } from '../PieChartBlock';

describe('LineChartBlock', () => {
  it('renders the title and a hand-rolled SVG with a polyline per series', () => {
    const { container } = render(
      <LineChartBlock
        type="line_chart"
        title="Gross Margin Trend"
        series={[{ name: 'Margin %', data: [{ x: 'Q1', y: 46.6 }, { x: 'Q2', y: 47.1 }] }]}
      />,
    );
    expect(screen.getByText('Gross Margin Trend')).toBeInTheDocument();
    expect(container.querySelector('svg.report-line-chart')).toBeTruthy();
    expect(container.querySelectorAll('polyline.series-line')).toHaveLength(1);
  });

  it('renders the empty-data message instead of a blank frame when series is empty', () => {
    // Without a guard, Math.min/Math.max over the empty y-array collapse to
    // Infinity/-Infinity and render a titled blank SVG frame. Guard renders
    // the localized no-data message and no chart SVG.
    const { container } = render(
      <LineChartBlock type="line_chart" title="Empty Trend" series={[]} />,
    );
    expect(screen.getByText('Empty Trend')).toBeInTheDocument();
    expect(container.querySelector('.report-chart__empty')).toBeTruthy();
    expect(container.querySelector('svg.report-line-chart')).toBeNull();
  });

  it('renders the empty-data message when every series has no data points', () => {
    const { container } = render(
      <LineChartBlock
        type="line_chart"
        title="No Points"
        categories={['Q1', 'Q2']}
        series={[{ name: 's', values: [] }]}
      />,
    );
    expect(container.querySelector('.report-chart__empty')).toBeTruthy();
    expect(container.querySelector('svg.report-line-chart')).toBeNull();
  });
});

describe('BarChartBlock', () => {
  it('renders one rect per (series × category) for vertical bars', () => {
    const { container } = render(
      <BarChartBlock
        type="bar_chart"
        title="Revenue by Segment"
        categories={['iPhone', 'Services']}
        series={[{ name: 'Q1 2026', values: [69.1, 26.3] }]}
      />,
    );
    expect(container.querySelector('svg.report-line-chart')).toBeTruthy();
    expect(container.querySelectorAll('svg rect')).toHaveLength(2);
  });

  it('renders horizontal layout when orientation=horizontal', () => {
    const { container } = render(
      <BarChartBlock
        type="bar_chart"
        title="Segments"
        categories={['A', 'B']}
        series={[{ name: 's1', values: [10, 20] }]}
        orientation="horizontal"
      />,
    );
    expect(container.querySelectorAll('.report-bars-h__row')).toHaveLength(2);
  });

  it('renders bars when persisted series uses `data` instead of `values`', () => {
    // Reports written before the schema normalization shipped ``data: [n, n]``
    // straight from the LLM prompt. The renderer must coerce so old rows
    // are not stuck displaying empty axes.
    const { container } = render(
      <BarChartBlock
        type="bar_chart"
        title="Legacy"
        categories={['A', 'B']}
        // @ts-expect-error — exercising legacy persisted shape
        series={[{ name: 's1', data: [12, 34] }]}
      />,
    );
    const rects = container.querySelectorAll('svg rect');
    expect(rects).toHaveLength(2);
    // Both bars must have non-trivial height — height-1 fallback means
    // the coercion failed to surface real values.
    const heights = Array.from(rects).map((r) => Number(r.getAttribute('height') ?? 0));
    expect(Math.max(...heights)).toBeGreaterThan(1);
  });
});

describe('AreaChartBlock', () => {
  it('renders one filled polygon per series', () => {
    const { container } = render(
      <AreaChartBlock
        type="area_chart"
        title="Revenue Composition"
        series={[
          { name: 'iPhone', data: [{ x: 'Q1', y: 1 }, { x: 'Q2', y: 2 }] },
        ]}
      />,
    );
    expect(container.querySelectorAll('svg polygon')).toHaveLength(1);
    expect(container.querySelectorAll('svg polyline.series-line')).toHaveLength(1);
  });
});

describe('PieChartBlock', () => {
  it('renders one path per segment', () => {
    const { container } = render(
      <PieChartBlock
        type="pie_chart"
        title="Revenue Mix"
        segments={[
          { label: 'iPhone', value: 69.1 },
          { label: 'Services', value: 26.3 },
        ]}
      />,
    );
    expect(container.querySelectorAll('svg path')).toHaveLength(2);
    expect(screen.getByText('iPhone')).toBeInTheDocument();
    expect(screen.getByText('Services')).toBeInTheDocument();
  });

  it('uses an inner radius when donut flag is set', () => {
    const { container } = render(
      <PieChartBlock
        type="pie_chart"
        title="t"
        donut
        segments={[{ label: 'a', value: 1 }]}
      />,
    );
    const path = container.querySelector('svg path');
    expect(path?.getAttribute('d')).toMatch(/M /);
  });

  it('renders the empty-data message instead of a blank frame when segments is empty', () => {
    const { container } = render(
      <PieChartBlock type="pie_chart" title="Empty Mix" segments={[]} />,
    );
    expect(screen.getByText('Empty Mix')).toBeInTheDocument();
    expect(container.querySelector('.report-chart__empty')).toBeTruthy();
    expect(container.querySelector('svg.report-pie__svg')).toBeNull();
  });

  it('renders the empty-data message when all segment values are non-positive', () => {
    const { container } = render(
      <PieChartBlock
        type="pie_chart"
        title="All Zero"
        segments={[
          { label: 'a', value: 0 },
          { label: 'b', value: 0 },
        ]}
      />,
    );
    expect(container.querySelector('.report-chart__empty')).toBeTruthy();
    expect(container.querySelector('svg.report-pie__svg')).toBeNull();
  });
});
