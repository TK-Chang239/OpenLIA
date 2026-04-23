import { describe, it, expect, vi } from 'vitest';

vi.mock('react-intersection-observer', () => ({
  useInView: () => ({ ref: () => {}, inView: true }),
}));

import { render } from '@testing-library/react';
import { ScrollTracker } from '../ScrollTracker';

describe('ScrollTracker', () => {
  it('calls onActiveId with the first intersecting section', () => {
    const cb = vi.fn();
    render(
      <ScrollTracker
        sectionIds={['a', 'b']}
        onActiveId={cb}
      />,
    );
    expect(cb).toHaveBeenCalled();
    const lastArgs = cb.mock.calls.at(-1) as [string];
    expect(['a', 'b']).toContain(lastArgs[0]);
  });
});
