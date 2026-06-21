import { useEffect, useRef } from "react";

interface Toaster {
  success(msg: string, opts?: { action?: { label: string; onClick: () => void } }): void;
  error(msg: string, opts?: { action?: { label: string; onClick: () => void } }): void;
  info(msg: string, opts?: { action?: { label: string; onClick: () => void } }): void;
}

interface Options {
  navigate: (path: string) => void;
  toast: Toaster;
  onAttachedReportChanged?: (data: { session_id: string; new_report_id: string }) => void;
}

export function useNotificationsStream({ navigate, toast, onAttachedReportChanged }: Options): void {
  // The caller (AppLayout's NotificationsWatcher) constructs `toast` and
  // `onAttachedReportChanged` inline on every render. If those were effect
  // deps the EventSource would be torn down and reopened on every re-render.
  // Stash the latest callbacks in a ref and keep the effect dep list empty so
  // the EventSource opens exactly once per mount and the listeners always call
  // the freshest callbacks.
  const cbRef = useRef<Options>({ navigate, toast, onAttachedReportChanged });
  cbRef.current = { navigate, toast, onAttachedReportChanged };

  useEffect(() => {
    const es = new EventSource("/notifications/stream");
    es.addEventListener("report.complete", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      cbRef.current.toast.success(`Report ready: ${data.title}`, {
        action: { label: "Open", onClick: () => cbRef.current.navigate(`/reports/${data.report_id}`) },
      });
    });
    es.addEventListener("report.failed", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      cbRef.current.toast.error(`Report failed: ${data.failure_reason}`, {
        action: { label: "Open", onClick: () => cbRef.current.navigate(`/reports/${data.report_id}`) },
      });
    });
    es.addEventListener("report.cancelled", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      cbRef.current.toast.info(`Report cancelled`, {
        action: { label: "Open", onClick: () => cbRef.current.navigate(`/reports/${data.report_id}`) },
      });
    });
    es.addEventListener("chat.attached_report_changed", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      cbRef.current.onAttachedReportChanged?.(data);
    });
    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
