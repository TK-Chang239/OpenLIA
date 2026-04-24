import { useEffect, useRef } from "react";

interface Props {
  children: React.ReactNode;
  autoscrollKey?: unknown;
}

export function MessageList({ children, autoscrollKey }: Props): JSX.Element {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    endRef.current?.scrollIntoView?.({
      block: "end",
      behavior: reduce ? "auto" : "smooth",
    });
  }, [autoscrollKey]);

  return (
    <div className="absolute inset-0 overflow-y-auto">
      <div
        data-testid="message-column"
        className="mx-auto max-w-[720px] space-y-2 px-6 py-8 pb-6"
      >
        {children}
        <div ref={endRef} />
      </div>
    </div>
  );
}
