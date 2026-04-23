import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReportCover } from '../ReportCover';

describe('ReportCover', () => {
  it('renders title, subtitle, tagline, key metrics, stats panel', () => {
    render(
      <ReportCover
        cover={{
          title: 'Apple Inc.',
          subtitle: 'Q1 2026',
          tagline: 'Strong quarter.',
          key_metrics: [{ label: 'Price', value: '$198.50' }],
          stats_panel: [{ label: 'Sector', value: 'Technology' }],
        }}
      />,
    );
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    expect(screen.getByText('Q1 2026')).toBeInTheDocument();
    expect(screen.getByText('Strong quarter.')).toBeInTheDocument();
    expect(screen.getByText('Price')).toBeInTheDocument();
    expect(screen.getByText('Sector')).toBeInTheDocument();
  });
});
