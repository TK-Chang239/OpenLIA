import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { QuoteBlock } from '../QuoteBlock';

describe('QuoteBlock', () => {
  it('renders the quote text', () => {
    render(<QuoteBlock text="We see broad-based momentum." />);
    expect(screen.getByText(/broad-based momentum/i)).toBeInTheDocument();
  });

  it('renders inline citation refs when source_ids provided', () => {
    render(<QuoteBlock text="We see broad-based momentum." source_ids={['1']} />);
    const link = screen.getByRole('link', { name: 'Source 1' });
    expect(link).toHaveAttribute('href', '#cite-1');
    expect(link).toHaveTextContent('[1]');
  });
});
