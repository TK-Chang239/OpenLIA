import { useState } from "react";

interface Props {
  onSaved: (reportId: string) => void;
  onError?: (message: string) => void;
}

export function OnDemandBriefingButton({ onSaved, onError }: Props) {
  const [running, setRunning] = useState(false);

  const start = async () => {
    setRunning(true);
    try {
      const response = await fetch(
        "/api/departments/morning-briefing/report",
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
          },
          body: JSON.stringify({}),
        },
      );
      if (!response.ok || !response.body) {
        onError?.(`HTTP ${response.status}`);
        return;
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent: string | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const raw of lines) {
          const line = raw.replace(/\r$/, "");
          if (line.startsWith("event:")) {
            currentEvent = line.slice("event:".length).trim();
          } else if (line.startsWith("data:")) {
            const data = line.slice("data:".length).trim();
            if (currentEvent === "report.saved") {
              try {
                const payload = JSON.parse(data) as { report_id: string };
                onSaved(payload.report_id);
              } catch {
                /* ignore malformed */
              }
            } else if (currentEvent === "report.error") {
              try {
                const payload = JSON.parse(data) as { message: string };
                onError?.(payload.message);
              } catch {
                onError?.("Report error");
              }
            }
          } else if (line === "") {
            currentEvent = null;
          }
        }
      }
    } catch (err) {
      onError?.((err as Error).message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <button
      type="button"
      className="px-4 py-2 rounded-md bg-primary text-primary-foreground disabled:opacity-50"
      disabled={running}
      onClick={start}
    >
      {running ? "Generating…" : "Generate Briefing"}
    </button>
  );
}
