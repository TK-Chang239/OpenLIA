import { useMemo, useState } from "react";

import { RecentReport } from "../../api/earnings-update";

import { ReportRowItem } from "./ReportRowItem";

interface Props {
  reports: RecentReport[];
  onBack: () => void;
  onOpenReport: (id: string) => void;
  onDownload: (id: string) => void;
  onRemove: (id: string) => Promise<void>;
}

function monthKey(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function EUCabinetView({
  reports,
  onBack,
  onOpenReport,
  onDownload,
  onRemove,
}: Props) {
  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return reports;
    return reports.filter(
      (r) =>
        (r.subject ?? "").toLowerCase().includes(needle) ||
        r.title.toLowerCase().includes(needle),
    );
  }, [q, reports]);

  const groups = useMemo(() => {
    const acc: Record<string, RecentReport[]> = {};
    for (const r of filtered) {
      const k = monthKey(r.created_at);
      (acc[k] ??= []).push(r);
    }
    return Object.entries(acc);
  }, [filtered]);

  return (
    <div className="fixed inset-0 bg-[--color-bg-base] z-50 overflow-y-auto">
      <header className="flex items-center justify-between h-14 px-6 border-b border-[--color-border-subtle]">
        <button
          type="button"
          onClick={onBack}
          className="text-sm text-[--color-accent-primary]"
        >
          ← Back to Earnings Updates
        </button>
        <h2 className="text-xl font-semibold">EU Cabinet</h2>
        <span className="w-32" />
      </header>
      <div className="px-6 py-4">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search reports..."
          className="w-full bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-md] px-3 h-9 text-sm text-[--color-text-primary]"
        />
      </div>
      {groups.map(([k, items]) => (
        <div key={k}>
          <h3 className="text-sm font-medium text-[--color-text-secondary] px-6 py-2">
            {k}
          </h3>
          {items.map((r) => (
            <ReportRowItem
              key={r.id}
              report={r}
              onOpen={onOpenReport}
              showExtras
              onDownload={onDownload}
              onRemove={(id) => void onRemove(id)}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
