import { describe, it, expect, vi, beforeAll } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('echarts-for-react', () => ({
  default: () => <div data-testid="echart" />,
}));
vi.mock('react-intersection-observer', () => ({
  useInView: () => ({ ref: () => {}, inView: false }),
}));

beforeAll(() => {
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      observe() {}
      disconnect() {}
      unobserve() {}
      root = null;
      rootMargin = '';
      thresholds = [];
      takeRecords() { return []; }
    },
  );
});

import { ReportRenderer } from '../ReportRenderer';
import type { ReportSchema } from '../../../api/reports';

const schema: ReportSchema = {
  schema_version: '2.0',
  department: 'equity_research',
  page_furniture: {
    header: { left: 'OpenLIA', right: 'Equity Research' },
    footer: { left: 'Gen', center: 'Page {page}', right: 'Internal' },
    disclaimer: 'Not advice.',
  },
  cover: {
    title: 'Apple Inc.',
    subtitle: 'Q1 2026',
    tagline: 'Strong.',
    ticker: 'AAPL',
  },
  sections: [
    {
      id: 'fin',
      title: 'Financial Overview',
      blocks: [{ type: 'text', content: 'Apple reported...' }],
    },
  ],
};

describe('ReportRenderer', () => {
  it('renders furniture, cover, TOC, and a section with blocks', () => {
    render(<ReportRenderer schema={schema} />);
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    expect(screen.getByText('Equity Research')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Financial Overview/ })).toBeInTheDocument();
    expect(screen.getByText('Apple reported...')).toBeInTheDocument();
    expect(screen.getByText('Not advice.')).toBeInTheDocument();
  });

  it('shows the skeleton while loading', () => {
    const { container } = render(<ReportRenderer loading sectionTitles={['a']} />);
    expect(container.querySelector('.report-skeleton')).toBeTruthy();
  });

  it('applies the provided report theme attribute', () => {
    const { container } = render(<ReportRenderer schema={schema} theme="dark" />);
    expect(container.querySelector('[data-report-theme="dark"]')).toBeTruthy();
  });

  it('renders the side rail when only citations are present', () => {
    const withCites: ReportSchema = {
      ...schema,
      citations: [
        { id: '1', title: 'Press release', source: 'Apple IR', url: 'https://example.com' },
      ],
    };
    const { container } = render(<ReportRenderer schema={withCites} />);
    expect(container.querySelector('.report__rail')).toBeTruthy();
    expect(container.querySelector('.report-rail__citations')).toBeTruthy();
    expect(container.querySelector('.report--3col')).toBeTruthy();
  });

  it('renders the v2.2 run summary section when present', () => {
    const withRunSummary: ReportSchema = {
      ...schema,
      run_summary: {
        engine_version: '0.2.0',
        template_id: 'stock_research_v2',
        template_name: 'Stock Research',
        composer_inputs: {},
        outcomes: [
          {
            task_type: 'section',
            task_name: 'Financial Overview',
            status: 'OK',
            duration_ms: 1200,
          },
        ],
        unsupported_requests_dismissed: [],
        unsupported_requests_slipped: [],
        total_duration_ms: 1200,
        cache_stats: {},
      },
    };
    const { container } = render(<ReportRenderer schema={withRunSummary} />);
    expect(container.querySelector('#run_summary')).toBeTruthy();
    expect(screen.getByText(/Engine v0\.2\.0/)).toBeInTheDocument();
  });

  it('hides verification history outside dev mode even when payload present', () => {
    const withHistory: ReportSchema = {
      ...schema,
      verification_history: {
        entries: [
          {
            issue: {
              issue_type: 'unsupported_claim',
              severity: 'warning',
              evidence: 'no source for claim',
              detector: 'llm',
            },
            raised_at_round: 1,
            final_resolution: 'resolved',
          },
        ],
      },
    };
    const { container } = render(<ReportRenderer schema={withHistory} />);
    expect(container.querySelector('#verification_history')).toBeFalsy();
  });

  it('renders verification history when dev mode is on', () => {
    const withHistory: ReportSchema = {
      ...schema,
      verification_history: {
        entries: [
          {
            issue: {
              issue_type: 'unsupported_claim',
              severity: 'warning',
              evidence: 'no source for claim',
              detector: 'llm',
            },
            raised_at_round: 1,
            final_resolution: 'resolved',
          },
        ],
      },
    };
    const { container } = render(<ReportRenderer schema={withHistory} devMode />);
    expect(container.querySelector('#verification_history')).toBeTruthy();
  });
});
