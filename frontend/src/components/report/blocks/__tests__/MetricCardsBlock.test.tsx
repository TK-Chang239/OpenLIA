import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MetricCardsBlock } from '../MetricCardsBlock';

describe('MetricCardsBlock', () => {
  it('renders a card per metric with label, value, and delta', () => {
    render(
      <MetricCardsBlock
        type="metric_cards"
        metrics={[
          { label: 'Revenue', value: '$124.3B', delta: '+31.1%', delta_direction: 'up' },
          { label: 'Net Income', value: '$36.3B', delta: '+53.8%', delta_direction: 'up' },
        ]}
      />,
    );
    expect(screen.getByText('Revenue')).toBeInTheDocument();
    expect(screen.getByText('$124.3B')).toBeInTheDocument();
    expect(screen.getAllByText(/\+\d/)).toHaveLength(2);
  });

  it('renders inline citation refs next to metric values', () => {
    render(
      <MetricCardsBlock
        type="metric_cards"
        metrics={[
          { label: 'Revenue', value: '$124.3B', source_ids: ['1'] },
        ]}
      />,
    );
    const link = screen.getByRole('link', { name: 'Source 1' });
    expect(link).toHaveAttribute('href', '#cite-1');
    expect(link).toHaveTextContent('[1]');
  });

  it('applies positive and negative delta classes', () => {
    const { container } = render(
      <MetricCardsBlock
        type="metric_cards"
        metrics={[
          { label: 'Up', value: '10', delta: '+5', delta_direction: 'up' },
          { label: 'Down', value: '10', delta: '-5', delta_direction: 'down' },
        ]}
      />,
    );
    expect(container.querySelector('.metric-card__delta--positive')).toBeTruthy();
    expect(container.querySelector('.metric-card__delta--negative')).toBeTruthy();
  });
});
