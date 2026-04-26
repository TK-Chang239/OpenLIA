import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { finish, getRequiredTiers, pollReview, runReview } from "../../api/setup";
import type { ReviewPoll } from "../../api/setup";
import { clearAllWizardStorage } from "../storage";

interface RequirementMapping {
  type: string;
  provider: string | null;
  confidence: number;
  provider_id?: string | null;
  provider_label?: string | null;
  provider_mode?: string | null;
  provider_url?: string | null;
  provider_status?: string | null;
}

interface DepartmentReadiness {
  id: string;
  state: "ready" | "gaps" | "disabled" | "blocked";
  note: string | null;
  basic: RequirementMapping[];
  advanced: RequirementMapping[];
  unmet: string[];
  check_status?: "pending" | "checked";
}

interface ReviewResult {
  summary: string;
  departments: DepartmentReadiness[];
}

export function ReviewStep({
  totalSteps,
  onBack,
}: {
  totalSteps: number;
  onBack: () => void;
}) {
  const [state, setState] = useState<"starting" | "running" | "complete" | "failed">("starting");
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [finishing, setFinishing] = useState(false);
  const [enabledDepartments, setEnabledDepartments] = useState<string[]>([]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    (async () => {
      try {
        const tiers = await getRequiredTiers();
        if (!cancelled) setEnabledDepartments(tiers?.enabled_departments ?? []);
      } catch {
        // Best-effort; pending list will be empty if this fails.
      }
      try {
        setState("running");
        const { review_id } = await runReview();
        const loop = async () => {
          if (cancelled) return;
          const poll: ReviewPoll = await pollReview(review_id);
          if (poll.result) {
            setResult(poll.result as ReviewResult);
          }
          if (poll.state === "complete") {
            setState("complete");
          } else if (poll.state === "failed") {
            setError(poll.error ?? "Review failed.");
            setState("failed");
          } else {
            timer = setTimeout(loop, 700);
          }
        };
        await loop();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to start review.");
        setState("failed");
      }
    })();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Build the rendered list: any departments returned by the server take
  // precedence; the rest fall back to the "pending" placeholder list.
  const rendered = useMemo<DepartmentReadiness[]>(() => {
    if (!result) {
      return enabledDepartments.map((id) => ({
        id,
        state: "ready",
        note: null,
        basic: [],
        advanced: [],
        unmet: [],
        check_status: "pending",
      }));
    }
    const seen = new Set(result.departments.map((d) => d.id));
    const trailing = enabledDepartments
      .filter((id) => !seen.has(id))
      .map<DepartmentReadiness>((id) => ({
        id,
        state: "ready",
        note: null,
        basic: [],
        advanced: [],
        unmet: [],
        check_status: "pending",
      }));
    return [...result.departments, ...trailing];
  }, [result, enabledDepartments]);

  const blockedDepts = useMemo(
    () => rendered.filter((d) => d.check_status === "checked" && d.state === "blocked"),
    [rendered],
  );

  const onFinish = async () => {
    setFinishing(true);
    try {
      const { redirect } = await finish();
      // Wizard's done — drop the per-step drafts so a future re-entry into
      // the setup route starts fresh.
      clearAllWizardStorage();
      window.location.href = redirect;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to finish.");
    } finally {
      setFinishing(false);
    }
  };

  const toggleExpand = (id: string) =>
    setExpanded((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const checkedCount = rendered.filter((d) => d.check_status === "checked").length;

  return (
    <WizardShell
      title="Review"
      stepIndex={totalSteps - 1}
      totalSteps={totalSteps}
      footer={
        <WizardFooter
          onBack={onBack}
          onNext={onFinish}
          nextLabel="Finish"
          nextDisabled={state !== "complete"}
          loading={finishing}
        />
      }
    >
      {state === "failed" ? (
        <p className="text-sm text-[--color-feedback-error]">{error}</p>
      ) : null}
      {state !== "failed" ? (
        <>
          <p className="text-sm text-[--color-text-primary] font-medium mb-1">
            {result?.summary ??
              (rendered.length > 0
                ? "Verifying each department against your configured providers…"
                : "Loading departments…")}
          </p>
          <p className="text-xs text-[--color-text-tertiary] mb-4">
            {state === "complete"
              ? "All departments checked."
              : `Checked ${checkedCount} of ${rendered.length}.`}
          </p>
          <div className="grid grid-cols-1 gap-3">
            {rendered.map((d) => (
              <DepartmentCard
                key={d.id}
                dept={d}
                expanded={expanded.has(d.id)}
                onToggle={() => toggleExpand(d.id)}
              />
            ))}
          </div>
          {blockedDepts.length > 0 ? (
            <div className="mt-4 px-3 py-2 rounded-[--radius-md] bg-[--color-feedback-warning]/10 border border-[--color-feedback-warning]/30 text-sm text-[--color-text-primary]">
              <p className="font-medium mb-1">
                {blockedDepts.length === 1
                  ? "1 department will be unavailable:"
                  : `${blockedDepts.length} departments will be unavailable:`}
              </p>
              <ul className="list-disc list-inside text-[--color-text-secondary]">
                {blockedDepts.map((d) => (
                  <li key={d.id} className="capitalize">
                    {d.id.replace(/_/g, " ")}
                    {d.unmet.length > 0 ? ` — needs ${d.unmet.join(", ")}` : ""}
                    {d.note ? ` — ${d.note}` : ""}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[--color-text-secondary]">
                You can finish setup now. To enable these later, add a provider that covers the
                missing capabilities in Settings → Data Providers.
              </p>
            </div>
          ) : null}
        </>
      ) : null}
    </WizardShell>
  );
}

function DepartmentCard({
  dept,
  expanded,
  onToggle,
}: {
  dept: DepartmentReadiness;
  expanded: boolean;
  onToggle: () => void;
}) {
  const checked = dept.check_status === "checked";
  const borderColor = !checked
    ? "var(--color-border-subtle)"
    : dept.state === "ready"
      ? "var(--color-feedback-success)"
      : dept.state === "gaps"
        ? "var(--color-feedback-warning)"
        : dept.state === "blocked"
          ? "var(--color-feedback-error)"
          : "var(--color-border-subtle)";
  const pillClass = !checked
    ? "bg-[--color-surface-active] text-[--color-text-tertiary]"
    : dept.state === "ready"
      ? "bg-[--color-feedback-success]/15 text-[--color-feedback-success]"
      : dept.state === "gaps"
        ? "bg-[--color-feedback-warning]/15 text-[--color-feedback-warning]"
        : dept.state === "blocked"
          ? "bg-[--color-feedback-error]/15 text-[--color-feedback-error]"
          : "bg-[--color-surface-active] text-[--color-text-tertiary]";
  const pillLabel = !checked ? "pending" : dept.state;
  const wirings = [...dept.basic, ...dept.advanced];
  return (
    <article
      className="border border-[--color-border-subtle] rounded-[--radius-md] bg-[--color-bg-elevated] p-4"
      style={{ borderLeftWidth: 3, borderLeftColor: borderColor }}
    >
      <header className="flex justify-between gap-3">
        <div className="min-w-0">
          <h4 className="text-sm font-semibold text-[--color-text-primary] capitalize">
            {dept.id.replace(/_/g, " ")}
          </h4>
          {checked && dept.unmet.length > 0 ? (
            <p className="text-xs text-[--color-text-secondary] mt-1 leading-relaxed">
              Unmet: {dept.unmet.join(", ")}
            </p>
          ) : null}
          {checked && dept.note ? (
            <p className="text-xs text-[--color-feedback-error] mt-1 leading-relaxed">{dept.note}</p>
          ) : null}
        </div>
        <span
          aria-label={`${dept.id} ${pillLabel}`}
          className={`text-xs px-2 py-0.5 rounded-full h-fit ${pillClass}`}
        >
          {pillLabel}
        </span>
      </header>
      {checked && wirings.length > 0 ? (
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          className="mt-3 inline-flex items-center gap-1 text-xs text-[--color-text-secondary] hover:text-[--color-text-primary]"
        >
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          {expanded ? "Hide adapter setup" : "Show adapter setup"}
        </button>
      ) : null}
      {checked && expanded ? <AdapterTable mappings={wirings} /> : null}
    </article>
  );
}

function AdapterTable({ mappings }: { mappings: RequirementMapping[] }) {
  return (
    <div className="mt-3 border border-[--color-border-subtle] rounded-[--radius-md] overflow-hidden">
      <table className="w-full text-xs">
        <thead className="bg-[--color-surface-hover] text-[--color-text-secondary]">
          <tr>
            <th className="text-left px-3 py-2 font-medium">Capability</th>
            <th className="text-left px-3 py-2 font-medium">Provider</th>
            <th className="text-left px-3 py-2 font-medium">Mode</th>
            <th className="text-left px-3 py-2 font-medium">Endpoint</th>
            <th className="text-left px-3 py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {mappings.map((m, i) => (
            <tr
              key={`${m.type}-${i}`}
              className="border-t border-[--color-border-subtle] text-[--color-text-primary]"
            >
              <td className="px-3 py-2 font-mono text-[10px]">{m.type}</td>
              <td className="px-3 py-2">{m.provider_label ?? m.provider ?? "—"}</td>
              <td className="px-3 py-2 capitalize">{m.provider_mode ?? "—"}</td>
              <td
                className="px-3 py-2 font-mono text-[10px] truncate max-w-[260px]"
                title={m.provider_url ?? ""}
              >
                {m.provider_url ?? "—"}
              </td>
              <td className="px-3 py-2">
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] ${
                    m.provider_status === "ok"
                      ? "bg-[--color-feedback-success]/15 text-[--color-feedback-success]"
                      : m.provider_status === "error"
                        ? "bg-[--color-feedback-error]/15 text-[--color-feedback-error]"
                        : "bg-[--color-surface-active] text-[--color-text-tertiary]"
                  }`}
                >
                  {m.provider_status ?? "unknown"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
