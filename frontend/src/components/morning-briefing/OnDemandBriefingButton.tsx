import { useEffect, useRef } from "react";

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
      className="px-4 py-2 rounded-md bg-primary text-primary-foreground disabled:opacity-50"
      disabled={running}
      onClick={onClick}
    >
      {running ? "Generating…" : "Generate Briefing"}
    </button>
  );
}
