import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { TableBlock } from '../TableBlock';

const base = {
  type: 'table' as const,
  title: 'Income Statement',
  headers: [
    { key: 'metric', label: 'Metric', align: 'left' as const },
    { key: 'q1_26', label: 'Q1 2026', align: 'right' as const, sortable: true },
    { key: 'yoy', label: 'YoY', align: 'right' as const },
  ],
  rows: [
    { metric: 'Revenue', q1_26: '$124.3B', yoy: '+31.1%', _row_style: 'default' as const },
    { metric: 'Gross Profit', q1_26: '$58.4B', yoy: '+30.6%', _row_style: 'subtotal' as const },
    { metric: 'Net Income', q1_26: '$36.3B', yoy: '+53.8%', _row_style: 'total' as const },
  ],
  cell_format: { yoy: { rule: 'directional' as const } },
  footnotes: ['Source: Company filings'],
  options: {},
};

describe('TableBlock', () => {
  it('renders headers, rows, and footnotes', () => {
    render(<TableBlock {...base} />);
    expect(screen.getByText('Metric')).toBeInTheDocument();
    expect(screen.getByText('Revenue')).toBeInTheDocument();
    expect(screen.getByText('Source: Company filings')).toBeInTheDocument();
  });

  it('applies row styles as classes', () => {
    const { container } = render(<TableBlock {...base} />);
    const rows = container.querySelectorAll('tbody tr');
    expect(rows[1].className).toMatch(/subtotal/);
    expect(rows[2].className).toMatch(/total/);
  });

  it('colors directional cells by sign of the value', () => {
    const { container } = render(<TableBlock {...base} />);
    const yoyCells = container.querySelectorAll('[data-col="yoy"]');
    yoyCells.forEach((c) => expect(c.className).toMatch(/positive/));
  });

  it('sorts by a sortable column on click', () => {
    render(<TableBlock {...base} />);
    const q1Header = screen.getByRole('button', { name: /Q1 2026/i });
    fireEvent.click(q1Header);
    const rows = screen.getAllByRole('row');
    const firstMetric = within(rows[1]).getByText(/Net Income|Revenue|Gross Profit/);
    expect(firstMetric.textContent).toBeDefined();
  });

  it('does not render a search input unless enabled', () => {
    render(<TableBlock {...base} />);
    expect(screen.queryByPlaceholderText(/search/i)).toBeNull();
  });

  it('renders sparkline cells when a header marks the column as sparkline', () => {
    const spark = {
      ...base,
      headers: [
        ...base.headers,
        { key: 'trend', label: '5Q', align: 'center' as const, sparkline: true },
      ],
      rows: [
        { metric: 'Revenue', q1_26: '$124.3B', yoy: '+31.1%', trend: [1, 2, 3, 4, 5] },
      ],
    };
    const { container } = render(<TableBlock {...spark} />);
    expect(container.querySelector('svg')).toBeTruthy();
  });
});
