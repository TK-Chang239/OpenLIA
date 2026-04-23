import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TextBlock } from '../TextBlock';

describe('TextBlock', () => {
  it('renders markdown paragraphs', () => {
    render(<TextBlock content="Apple **reported** revenue." />);
    expect(screen.getByText(/reported/i).tagName.toLowerCase()).toBe('strong');
  });

  it('renders lists', () => {
    render(<TextBlock content={'- one\n- two'} />);
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
  });

  it('colors positive signed percentages', () => {
    const { container } = render(<TextBlock content="Revenue grew +31.1% YoY." />);
    const span = container.querySelector('.report-number--positive');
    expect(span?.textContent).toBe('+31.1%');
  });

  it('colors negative signed percentages', () => {
    const { container } = render(<TextBlock content="Margins fell -2.3% QoQ." />);
    const span = container.querySelector('.report-number--negative');
    expect(span?.textContent).toBe('-2.3%');
  });
});
