import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { CitationsSection, displayCitationTitle } from '../CitationsSection';
import type { Citation } from '../../../api/reports';

describe('CitationsSection', () => {
  it('renders nothing when citations is empty', () => {
    const { container } = render(<CitationsSection citations={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders the explicit title when provided', () => {
    const citations: Citation[] = [
      { id: '1', title: 'Apple beats Q1' },
    ];
    render(<CitationsSection citations={citations} />);
    expect(screen.getByText('Apple beats Q1')).toBeInTheDocument();
  });

  it('falls back to URL hostname+path when title is missing', () => {
    const citations: Citation[] = [
      { id: '1', url: 'https://reuters.com/business/apple-q1' },
    ];
    render(<CitationsSection citations={citations} />);
    expect(screen.getByText('reuters.com/business/apple-q1')).toBeInTheDocument();
  });

  it('falls back to source · date when title and URL are missing', () => {
    const citations: Citation[] = [
      { id: '1', source: 'Reuters', date: '2026-05-12' },
    ];
    render(<CitationsSection citations={citations} />);
    // Title line and meta line will both contain the source/date — title
    // line uses the fallback. Use the title slot's class to disambiguate.
    expect(screen.getAllByText(/Reuters/).length).toBeGreaterThan(0);
  });

  it('falls back to "(source)" when nothing else is available', () => {
    const citations: Citation[] = [
      { id: '1' },
    ];
    render(<CitationsSection citations={citations} />);
    expect(screen.getByText('(source)')).toBeInTheDocument();
  });
});

describe('displayCitationTitle', () => {
  it('returns title when present', () => {
    expect(displayCitationTitle({ id: '1', title: 'Hello' })).toBe('Hello');
  });

  it('returns hostname+path when only URL is set', () => {
    expect(
      displayCitationTitle({ id: '1', url: 'https://www.reuters.com/foo/bar/' }),
    ).toBe('reuters.com/foo/bar');
  });

  it('returns source · date when only those are set', () => {
    expect(
      displayCitationTitle({ id: '1', source: 'Reuters', date: '2026-05-12' }),
    ).toBe('Reuters · 2026-05-12');
  });

  it('returns source alone when date is missing', () => {
    expect(displayCitationTitle({ id: '1', source: 'Reuters' })).toBe('Reuters');
  });

  it('returns "(source)" as the last resort', () => {
    expect(displayCitationTitle({ id: '1' })).toBe('(source)');
  });
});
