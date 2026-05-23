/**
 * V23ReportFullScreen — full-screen overlay for reading a v2.3 report.
 *
 * Wraps <V23ReportView> with page chrome (back button, print/docx,
 * outline rail) and self-fetches the payload from a runId so the
 * overlay can mount from the URL alone (?run_id_v23=&view=report)
 * without depending on parent state.
 */
import { ArrowLeft, Download, Printer } from "lucide-react";
import { type JSX, useCallback, useEffect, useState } from "react";

import {
  type V23RunPayload,
  getV23RunPayload,
  v23DocxUrl,
} from "../../api/equity-research-v2-3";

import { V23ReportView } from "./V23ReportView";

interface Props {
  runId: string;
  onClose: () => void;
}

export function V23ReportFullScreen({ runId, onClose }: Props): JSX.Element {
  const [payload, setPayload] = useState<V23RunPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setPayload(null);
    getV23RunPayload(runId)
      .then((p) => {
        if (!cancelled) setPayload(p);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "failed to load report");
      });
    return () => {
      cancelled = true;
    };
  }, [runId]);

  // Esc closes the overlay; mirrors the v2.2 FileViewer pattern.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const print = useCallback(() => {
    if (typeof window !== "undefined") window.print();
  }, []);

  return (
    <div
      data-testid="er-v2-3-report-fullscreen"
      data-print-target="v23-report-fullscreen"
      className="fixed inset-0 z-50 flex flex-col bg-[--color-bg-base]"
    >
      <header
        data-print-hide="true"
        className="flex h-12 flex-shrink-0 items-center justify-between gap-3 border-b border-[--color-border-subtle] px-4"
      >
        <button
          type="button"
          onClick={onClose}
          data-testid="er-v2-3-report-fullscreen-close"
          className="inline-flex h-8 items-center gap-[6px] rounded-md px-2 font-mono text-[11px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
        >
          <ArrowLeft size={13} /> Back
        </button>
        <div className="flex-1 truncate text-center font-mono text-[10.5px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
          {payload
            ? `${payload.tickers.join(", ")} · ${payload.report_type}`
            : "Loading…"}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={print}
            data-testid="er-v2-3-report-fullscreen-print"
            className="inline-flex h-8 items-center gap-[6px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-2 font-mono text-[10.5px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-[--color-border-strong] hover:text-[--color-text-primary]"
          >
            <Printer size={11} /> Print
          </button>
          <a
            href={v23DocxUrl(runId)}
            download
            data-testid="er-v2-3-report-fullscreen-docx"
            className="inline-flex h-8 items-center gap-[6px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-2 font-mono text-[10.5px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-[--color-border-strong] hover:text-[--color-text-primary]"
          >
            <Download size={11} /> .docx
          </a>
        </div>
      </header>

      {error !== null ? (
        <div
          role="alert"
          className="m-6 rounded-md border border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] px-4 py-3 text-[13px] text-[--color-feedback-danger]"
        >
          Could not load report: {error}
        </div>
      ) : payload === null ? (
        <div className="flex flex-1 items-center justify-center font-mono text-[11px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
          Loading report…
        </div>
      ) : (
        <div className="flex flex-1 min-h-0 overflow-hidden">
          <Outline payload={payload} />
          <div className="flex-1 overflow-y-auto px-6 py-6">
            <div className="mx-auto w-full max-w-[820px]">
              <V23ReportView payload={payload} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Outline({ payload }: { payload: V23RunPayload }): JSX.Element {
  return (
    <aside
      data-print-hide="true"
      data-testid="er-v2-3-report-outline"
      className="hidden w-[200px] flex-shrink-0 overflow-y-auto border-r border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-4 lg:block"
    >
      <div className="mb-2 font-mono text-[9.5px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
        Outline
      </div>
      <ul className="flex flex-col gap-[2px]">
        {payload.sections.map((s) => (
          <li key={s.id}>
            <a
              href={`#section-${s.id}`}
              className="block rounded-sm px-2 py-1 text-[12px] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
            >
              {s.title}
            </a>
          </li>
        ))}
      </ul>
    </aside>
  );
}
