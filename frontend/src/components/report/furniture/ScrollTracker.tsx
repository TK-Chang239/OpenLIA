import { useEffect, useRef } from 'react';

export interface ScrollTrackerProps {
  sectionIds: string[];
  onActiveId: (id: string) => void;
}

/** Watches actual section elements (looked up by id) via IntersectionObserver
 *  and reports which one is currently in the active band of the viewport.
 *  Renders nothing — consumers just place this anywhere inside the report. */
export function ScrollTracker({ sectionIds, onActiveId }: ScrollTrackerProps) {
  const callbackRef = useRef(onActiveId);
  callbackRef.current = onActiveId;

  useEffect(() => {
    if (sectionIds.length === 0) return;
    const elements = sectionIds
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null);
    if (elements.length === 0) return;

    const seen = new Map<string, IntersectionObserverEntry>();

    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) seen.set(e.target.id, e);
        const active = sectionIds
          .map((id) => seen.get(id))
          .filter((e): e is IntersectionObserverEntry => !!e && e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (active) callbackRef.current(active.target.id);
      },
      { rootMargin: '-15% 0px -65% 0px', threshold: [0, 0.1, 0.5, 1] },
    );

    elements.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [sectionIds]);

  return null;
}
