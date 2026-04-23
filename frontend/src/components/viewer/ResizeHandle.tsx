import { useCallback, useRef } from "react";

interface Props {
  onWidthChange: (next: number) => void;
  viewportWidth: number;
}

export function ResizeHandle({ onWidthChange, viewportWidth }: Props): JSX.Element {
  const dragging = useRef(false);

  const onDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    dragging.current = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, []);

  const onMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!dragging.current) return;
      const next = Math.max(360, Math.min(viewportWidth * 0.7, viewportWidth - e.clientX));
      onWidthChange(next);
      try {
        localStorage.setItem("fileviewer_width", String(Math.round(next)));
      } catch {}
    },
    [onWidthChange, viewportWidth],
  );

  const onUp = useCallback(() => {
    dragging.current = false;
  }, []);

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize file viewer"
      onPointerDown={onDown}
      onPointerMove={onMove}
      onPointerUp={onUp}
      className="absolute inset-y-0 left-0 z-10 w-1 cursor-col-resize hover:bg-[--color-border-secondary]"
    />
  );
}
