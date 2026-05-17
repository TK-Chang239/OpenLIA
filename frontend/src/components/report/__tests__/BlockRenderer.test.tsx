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

  it('wraps chart blocks with data-block-path when path is provided', () => {
    const { container } = render(
      <BlockRenderer
        block={{ type: 'pie_chart', title: 'x', segments: [{ label: 'a', value: 1 }] }}
        blockPath="0-2"
      />,
    );
    const wrapper = container.querySelector('[data-block-path="0-2"]');
    expect(wrapper).not.toBeNull();
    expect(wrapper?.getAttribute('data-block-type')).toBe('pie_chart');
  });

  it('does not wrap text blocks with data-block-path', () => {
    const { container } = render(
      <BlockRenderer block={{ type: 'text', content: 'hi' }} blockPath="0-0" />,
    );
    expect(container.querySelector('[data-block-path]')).toBeNull();
  });
});
