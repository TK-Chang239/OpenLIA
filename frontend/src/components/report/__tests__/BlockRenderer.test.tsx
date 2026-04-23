import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('echarts-for-react', () => ({
  default: ({ option }: any) => (
    <div data-testid="echart" data-option={JSON.stringify(option)} />
  ),
}));

import { BlockRenderer } from '../BlockRenderer';

describe('BlockRenderer', () => {
  it('renders a text block', () => {
    render(<BlockRenderer block={{ type: 'text', content: 'hello' }} />);
    expect(screen.getByText('hello')).toBeInTheDocument();
  });

  it('renders a table block', () => {
    render(
      <BlockRenderer
        block={{
          type: 'table',
          title: 'T',
          headers: [{ key: 'a', label: 'A' }],
          rows: [{ a: 'row1' }],
        }}
      />,
    );
    expect(screen.getByText('T')).toBeInTheDocument();
    expect(screen.getByText('row1')).toBeInTheDocument();
  });

  it('renders a group that nests other blocks', () => {
    render(
      <BlockRenderer
        block={{
          type: 'group',
          columns: 2,
          blocks: [
            { type: 'text', content: 'left' },
            { type: 'text', content: 'right' },
          ],
        }}
      />,
    );
    expect(screen.getByText('left')).toBeInTheDocument();
    expect(screen.getByText('right')).toBeInTheDocument();
  });

  it('renders an unknown block type as a visible error', () => {
    render(<BlockRenderer block={{ type: 'movie', src: 'x' } as any} />);
    expect(screen.getByText(/unsupported block/i)).toBeInTheDocument();
  });
});
