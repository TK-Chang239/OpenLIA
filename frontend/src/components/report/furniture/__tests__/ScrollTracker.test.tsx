import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import { ScrollTracker } from '../ScrollTracker';

describe('ScrollTracker', () => {
  let observed: HTMLElement[] = [];
  let lastCallback: IntersectionObserverCallback | null = null;

  beforeEach(() => {
    observed = [];
    lastCallback = null;
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        constructor(cb: IntersectionObserverCallback) {
          lastCallback = cb;
        }
        observe(el: HTMLElement) {
          observed.push(el);
        }
        disconnect() {}
        unobserve() {}
        root = null;
        rootMargin = '';
        thresholds = [];
        takeRecords() { return []; }
      },
    );
    document.body.innerHTML = `<section id="a"></section><section id="b"></section>`;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.body.innerHTML = '';
  });

  it('observes the section elements and reports the topmost intersecting one', () => {
    const cb = vi.fn();
    render(<ScrollTracker sectionIds={['a', 'b']} onActiveId={cb} />);
    expect(observed.map((e) => e.id)).toEqual(['a', 'b']);

    const aEl = document.getElementById('a')!;
    const bEl = document.getElementById('b')!;
    lastCallback!(
      [
        { target: aEl, isIntersecting: true, boundingClientRect: { top: 50 } } as unknown as IntersectionObserverEntry,
        { target: bEl, isIntersecting: true, boundingClientRect: { top: 200 } } as unknown as IntersectionObserverEntry,
      ],
      {} as IntersectionObserver,
    );
    expect(cb).toHaveBeenLastCalledWith('a');
  });
});
