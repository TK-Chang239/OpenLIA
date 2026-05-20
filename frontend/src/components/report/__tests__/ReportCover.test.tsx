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

  it('renders the deterministic consensus block when consensus fields are set', () => {
    render(
      <ReportCover
        cover={{
          title: 'Apple Inc.',
          subtitle: 'Technology',
          tagline: 'Strong quarter.',
          consensus_rating: 'Buy',
          consensus_target_mean: 245.5,
          consensus_upside_pct: 0.225,
          consensus_source_ids: ['c1'],
        }}
      />,
    );
    expect(screen.getByTestId('report-cover-consensus')).toBeInTheDocument();
    expect(screen.getByText('Buy')).toBeInTheDocument();
    expect(screen.getByText('$245.50')).toBeInTheDocument();
    expect(screen.getByText('+22.5%')).toBeInTheDocument();
  });

  it('omits the consensus block entirely when all consensus fields are absent', () => {
    render(
      <ReportCover
        cover={{
          title: 'Microcap Inc.',
          subtitle: 'Industrials',
          tagline: 'No analyst coverage.',
        }}
      />,
    );
    expect(screen.queryByTestId('report-cover-consensus')).not.toBeInTheDocument();
  });

  it('renders a negative-toned upside when consensus_upside_pct is negative', () => {
    render(
      <ReportCover
        cover={{
          title: 'Stretched Co.',
          subtitle: 'Consumer',
          tagline: 'Trading above target.',
          consensus_rating: 'Hold',
          consensus_target_mean: 100.0,
          consensus_upside_pct: -0.12,
          consensus_source_ids: ['c1'],
        }}
      />,
    );
    const upside = screen.getByText('-12.0%');
    expect(upside).toBeInTheDocument();
    expect(upside.getAttribute('data-tone')).toBe('negative');
  });
});
