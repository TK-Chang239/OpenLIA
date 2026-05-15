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
});
