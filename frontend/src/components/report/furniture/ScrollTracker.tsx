import { useEffect } from 'react';
import { useInView } from 'react-intersection-observer';

export interface ScrollTrackerProps {
  sectionIds: string[];
  onActiveId: (id: string) => void;
}

interface SentinelProps {
  id: string;
  onVisible: (id: string) => void;
}

function SectionSentinel({ id, onVisible }: SentinelProps) {
  const { ref, inView } = useInView({ rootMargin: '-40% 0px -50% 0px' });
  useEffect(() => {
    if (inView) onVisible(id);
  }, [id, inView, onVisible]);
  return <span ref={ref} data-scroll-sentinel={id} style={{ display: 'block', height: 0 }} />;
}

export function ScrollTracker({ sectionIds, onActiveId }: ScrollTrackerProps) {
  return (
    <>
      {sectionIds.map((id) => (
        <SectionSentinel key={id} id={id} onVisible={onActiveId} />
      ))}
    </>
  );
}
