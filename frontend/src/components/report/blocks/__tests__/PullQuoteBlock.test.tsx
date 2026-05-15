import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { PullQuoteBlock } from '../PullQuoteBlock';

describe('PullQuoteBlock', () => {
  it('renders the quote text', () => {
    render(<PullQuoteBlock type="pull_quote" text="Innovation drives growth." />);
    expect(screen.getByText('Innovation drives growth.')).toBeInTheDocument();
  });

  it('renders inline citation refs when source_ids provided', () => {
    render(
      <PullQuoteBlock
        type="pull_quote"
        text="Innovation drives growth."
        source_ids={['1']}
      />,
    );
    const link = screen.getByRole('link', { name: 'Source 1' });
    expect(link).toHaveAttribute('href', '#cite-1');
    expect(link).toHaveTextContent('[1]');
  });
});
