import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KeyFindingBlock } from '../KeyFindingBlock';

describe('KeyFindingBlock', () => {
  it('renders markdown content inside a highlighted callout', () => {
    const { container } = render(
      <KeyFindingBlock type="key_finding" content="iPhone **revenue** grew 49% YoY." />,
    );
    expect(container.querySelector('.key-finding')).toBeTruthy();
    expect(screen.getByText(/revenue/i).tagName.toLowerCase()).toBe('strong');
  });

  it('renders inline citation refs when source_ids provided', () => {
    render(
      <KeyFindingBlock
        type="key_finding"
        content="Margins expanded materially."
        source_ids={['1']}
      />,
    );
    const link = screen.getByRole('link', { name: 'Source 1' });
    expect(link).toHaveAttribute('href', '#cite-1');
    expect(link).toHaveTextContent('[1]');
  });
});
