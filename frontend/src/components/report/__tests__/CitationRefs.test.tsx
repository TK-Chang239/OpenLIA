import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { CitationRefs } from '../CitationRefs';

describe('CitationRefs', () => {
  it('renders nothing when ids is undefined', () => {
    const { container } = render(<CitationRefs ids={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when ids is empty', () => {
    const { container } = render(<CitationRefs ids={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders one anchor per id with bracketed text', () => {
    render(<CitationRefs ids={['1', '2', '3']} />);
    expect(screen.getByText('[1]')).toBeInTheDocument();
    expect(screen.getByText('[2]')).toBeInTheDocument();
    expect(screen.getByText('[3]')).toBeInTheDocument();
  });

  it('href is #cite-{id} and aria-label is "Source {id}"', () => {
    render(<CitationRefs ids={['7']} />);
    const link = screen.getByRole('link', { name: 'Source 7' });
    expect(link).toHaveAttribute('href', '#cite-7');
    expect(link).toHaveClass('citation-ref');
  });

  it('wraps anchors in a .citation-refs container span', () => {
    const { container } = render(<CitationRefs ids={['1']} />);
    const wrapper = container.querySelector('.citation-refs');
    expect(wrapper).toBeTruthy();
    expect(wrapper?.querySelectorAll('a.citation-ref')).toHaveLength(1);
  });

  it('strips the leading "c" prefix from displayed labels (anchor keeps full id)', () => {
    render(<CitationRefs ids={['c14', 'c16']} />);
    expect(screen.getByText('[14]')).toBeInTheDocument();
    expect(screen.getByText('[16]')).toBeInTheDocument();
    expect(screen.queryByText('[c14]')).toBeNull();
    expect(screen.getByRole('link', { name: 'Source c14' })).toHaveAttribute(
      'href',
      '#cite-c14',
    );
  });
});
