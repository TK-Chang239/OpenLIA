import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GroupBlock, type GroupChildRenderer } from '../GroupBlock';

const child = (label: string, type: string) => ({ type, _label: label } as any);

const renderer: GroupChildRenderer = (b: any, forced) => (
  <div data-testid={`child-${b._label}`} data-forced-height={forced ?? 'none'}>
    {b.type}
  </div>
);

describe('GroupBlock', () => {
  it('renders children in N columns', () => {
    const { container } = render(
      <GroupBlock
        type="group"
        columns={3}
        blocks={[child('a', 'text'), child('b', 'text'), child('c', 'text')]}
        renderChild={renderer}
      />,
    );
    const grid = container.querySelector('.group-block') as HTMLElement;
    expect(grid.style.gridTemplateColumns).toContain('3');
  });

  it('forces medium chart height when chart and table are mixed', () => {
    render(
      <GroupBlock
        type="group"
        columns={2}
        blocks={[child('chart', 'line_chart'), child('table', 'table')]}
        renderChild={renderer}
      />,
    );
    expect(screen.getByTestId('child-chart').dataset.forcedHeight).toBe('medium');
    expect(screen.getByTestId('child-table').dataset.forcedHeight).toBe('none');
  });

  it('normalizes all charts to the tallest declared height', () => {
    const withOpts = (label: string, height: 'small' | 'medium' | 'tall') => ({
      type: 'bar_chart',
      _label: label,
      options: { height },
    });
    render(
      <GroupBlock
        type="group"
        columns={2}
        blocks={[withOpts('a', 'small'), withOpts('b', 'tall')] as any}
        renderChild={renderer}
      />,
    );
    expect(screen.getByTestId('child-a').dataset.forcedHeight).toBe('tall');
    expect(screen.getByTestId('child-b').dataset.forcedHeight).toBe('tall');
  });

  it('leaves all-tables un-normalized', () => {
    render(
      <GroupBlock
        type="group"
        columns={2}
        blocks={[child('t1', 'table'), child('t2', 'table')]}
        renderChild={renderer}
      />,
    );
    expect(screen.getByTestId('child-t1').dataset.forcedHeight).toBe('none');
    expect(screen.getByTestId('child-t2').dataset.forcedHeight).toBe('none');
  });
});
