import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RatingBadgeBlock } from '../RatingBadgeBlock';

describe('RatingBadgeBlock', () => {
  it('renders positive rating with positive class', () => {
    const { container } = render(
      <RatingBadgeBlock type="rating_badge" rating="Overweight" />,
    );
    expect(container.querySelector('.rating-badge--positive')).toBeTruthy();
    expect(screen.getByText('Overweight')).toBeInTheDocument();
  });

  it('renders neutral rating with neutral class', () => {
    const { container } = render(
      <RatingBadgeBlock type="rating_badge" rating="Hold" />,
    );
    expect(container.querySelector('.rating-badge--neutral')).toBeTruthy();
  });

  it('renders negative rating with negative class', () => {
    const { container } = render(
      <RatingBadgeBlock type="rating_badge" rating="Sell" />,
    );
    expect(container.querySelector('.rating-badge--negative')).toBeTruthy();
  });

  it('shows previous rating struck through when provided', () => {
    render(
      <RatingBadgeBlock
        type="rating_badge"
        rating="Overweight"
        previous_rating="Equal Weight"
        change_date="2026-04-11"
      />,
    );
    const prev = screen.getByText('Equal Weight');
    expect(prev.tagName.toLowerCase()).toBe('s');
  });
});
