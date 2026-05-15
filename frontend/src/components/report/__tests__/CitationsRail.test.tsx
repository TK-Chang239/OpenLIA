import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { CitationsRail } from '../CitationsRail';
import type { Citation } from '../../../api/reports';

describe('CitationsRail', () => {
  it('renders nothing when citations is empty', () => {
    const { container } = render(<CitationsRail citations={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders one item per citation with number badge and title', () => {
    const citations: Citation[] = [
      { id: '1', title: 'First source' },
      { id: '2', title: 'Second source' },
      { id: '3', title: 'Third source' },
    ];
    render(<CitationsRail citations={citations} />);
    expect(screen.getByText('Sources')).toBeInTheDocument();
    expect(screen.getByText('[1]')).toBeInTheDocument();
    expect(screen.getByText('[2]')).toBeInTheDocument();
    expect(screen.getByText('[3]')).toBeInTheDocument();
    expect(screen.getByText('First source')).toBeInTheDocument();
    expect(screen.getByText('Second source')).toBeInTheDocument();
    expect(screen.getByText('Third source')).toBeInTheDocument();
  });

  it('renders external links with target=_blank and rel=noreferrer noopener', () => {
    const citations: Citation[] = [
      {
        id: '1',
        title: 'External source',
        url: 'https://example.com/article',
      },
    ];
    render(<CitationsRail citations={citations} />);
    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', 'https://example.com/article');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noreferrer noopener');
  });

  it('renders in-page anchor when no url is present', () => {
    const citations: Citation[] = [
      { id: '7', title: 'Internal only' },
    ];
    render(<CitationsRail citations={citations} />);
    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '#cite-7');
    expect(link).not.toHaveAttribute('target');
  });

  it('renders meta line with source and date when present', () => {
    const citations: Citation[] = [
      {
        id: '1',
        title: 'A title',
        source: 'Reuters',
        date: '2026-05-10',
      },
    ];
    render(<CitationsRail citations={citations} />);
    expect(screen.getByText('Reuters · 2026-05-10')).toBeInTheDocument();
  });

  it('title attribute hover preview includes title, source, date, and url', () => {
    const citations: Citation[] = [
      {
        id: '1',
        title: 'Apple Q1 results',
        source: 'Reuters',
        date: '2026-05-10',
        url: 'https://example.com/apple',
      },
    ];
    render(<CitationsRail citations={citations} />);
    const link = screen.getByRole('link');
    const preview = link.getAttribute('title') ?? '';
    expect(preview).toContain('Apple Q1 results');
    expect(preview).toContain('Reuters');
    expect(preview).toContain('2026-05-10');
    expect(preview).toContain('https://example.com/apple');
  });
});
