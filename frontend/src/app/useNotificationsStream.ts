import { useEffect } from "react";

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
  useEffect(() => {
    const es = new EventSource("/notifications/stream");
    es.addEventListener("report.complete", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      toast.success(`Report ready: ${data.title}`, {
        action: { label: "Open", onClick: () => navigate(`/reports/${data.report_id}`) },
      });
    });
    es.addEventListener("report.failed", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      toast.error(`Report failed: ${data.failure_reason}`, {
        action: { label: "Open", onClick: () => navigate(`/reports/${data.report_id}`) },
      });
    });
    es.addEventListener("report.cancelled", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      toast.info(`Report cancelled`, {
        action: { label: "Open", onClick: () => navigate(`/reports/${data.report_id}`) },
      });
    });
    es.addEventListener("chat.attached_report_changed", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      onAttachedReportChanged?.(data);
    });
    return () => es.close();
  }, [navigate, toast, onAttachedReportChanged]);
}
