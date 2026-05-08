import { useEffect, useRef } from "react";
import { Plus } from "lucide-react";

import { useReportStream } from "../report/useReportStream";

interface Props {
  onSaved: (reportId: string) => void;
  onError?: (message: string) => void;
}

export function OnDemandBriefingButton({ onSaved, onError }: Props) {
  const { state, start, reset } = useReportStream();
  const seenIdRef = useRef<string | null>(null);
  const seenErrorRef = useRef<string | null>(null);
  const running = state.status === "starting" || state.status === "writing";

  useEffect(() => {
    if (
      state.status === "complete" &&
      state.reportId &&
      seenIdRef.current !== state.reportId
    ) {
      seenIdRef.current = state.reportId;
      onSaved(state.reportId);
      reset();
    } else if (
      state.status === "error" &&
      state.errorMessage &&
      seenErrorRef.current !== state.errorMessage
    ) {
      seenErrorRef.current = state.errorMessage;
      onError?.(state.errorMessage);
      reset();
    }
  }, [
    state.status,
    state.reportId,
    state.errorMessage,
    onSaved,
    onError,
    reset,
  ]);

  const onClick = () => {
    seenIdRef.current = null;
    seenErrorRef.current = null;
    start({
      url: "/api/departments/morning-briefing/report",
      body: {},
    });
  };

  return (
    <button
      type="button"
      disabled={running}
      onClick={onClick}
      className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border bg-transparent text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] disabled:opacity-50"
      style={{ borderColor: "var(--color-border-secondary)" }}
    >
      <Plus size={13} strokeWidth={1.8} />
      {running ? "Generating…" : "Run now"}
    </button>
  );
}
