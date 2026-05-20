import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReportCover } from '../ReportCover';

describe('ReportCover', () => {
  it('renders eyebrow, title, subtitle, tagline, doc-meta strip, and TL;DR card', () => {
    render(
      <ReportCover
        cover={{
          title: 'Apple Inc.',
          subtitle: 'Q1 2026',
          eyebrow: 'Stock Initiation · Apr 29',
          tagline: 'Strong quarter.',
          tldr: ['We initiate at Buy, $245 PT.'],
          key_metrics: [{ label: 'Price', value: '$198.50' }],
        }}
      />,
    );
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    expect(screen.getByText('Q1 2026')).toBeInTheDocument();
    expect(screen.getByText('Stock Initiation · Apr 29')).toBeInTheDocument();
    expect(screen.getByText('Strong quarter.')).toBeInTheDocument();
    expect(screen.getByText('Price')).toBeInTheDocument();
    expect(screen.getByText('We initiate at Buy, $245 PT.')).toBeInTheDocument();
    expect(screen.getByText('Executive Summary')).toBeInTheDocument();
  });

  it('uses custom tldr_label when provided', () => {
    render(
      <ReportCover
        cover={{
          title: 'AAPL · Q1',
          subtitle: 'Earnings',
          tagline: 'Beat on Services.',
          tldr_label: 'Verdict',
          tldr: ['Maintain Buy.'],
        }}
      />,
    );
    expect(screen.getByText('Verdict')).toBeInTheDocument();
  });
});
