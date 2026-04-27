import { useEffect, useMemo, useState } from "react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { finish } from "../../api/setup";
import { getReview, scopeAll } from "../../api/connectors";
import type {
  Category,
  ReviewCategoryRow,
  ReviewDepartmentRow,
  ReviewResponse,
} from "../../api/connectors";
import { clearAllWizardStorage } from "../storage";

const CATEGORY_ORDER: Category[] = ["financial", "news", "social", "web_search"];

const CATEGORY_LABEL: Record<Category, string> = {
  financial: "financial",
  news: "news",
  social: "social",
  web_search: "web search",
};

export function ReviewStep({
  totalSteps,
  onBack,
}: {
  totalSteps: number;
  onBack: () => void;
}) {
  const [review, setReview] = useState<ReviewResponse | null>(null);
  const [scoping, setScoping] = useState(true);
  const [rescoping, setRescoping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [finishing, setFinishing] = useState(false);

  const loadReview = async () => {
    setError(null);
    try {
      await scopeAll();
      const resp = await getReview();
      setReview(resp);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load review.");
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setScoping(true);
      try {
        await scopeAll();
        if (cancelled) return;
        const resp = await getReview();
        if (cancelled) return;
        setReview(resp);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load review.");
      } finally {
        if (!cancelled) setScoping(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onRescope = async () => {
    setRescoping(true);
    try {
      await loadReview();
    } finally {
      setRescoping(false);
    }
  };

  const sortedDepartments = useMemo<ReviewDepartmentRow[]>(() => {
    if (!review) return [];
    return [...review.departments].sort((a, b) => {
      if (a.ready !== b.ready) return a.ready ? 1 : -1;
      return a.department_id.localeCompare(b.department_id);
    });
  }, [review]);

  const onFinish = async () => {
    setFinishing(true);
    try {
      const { redirect } = await finish();
      clearAllWizardStorage();
      window.location.href = redirect;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to finish.");
    } finally {
      setFinishing(false);
    }
  };

  const ready = review !== null && !scoping;

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
          nextDisabled={!ready}
          loading={finishing}
        />
      }
    >
      {error ? (
        <p className="mb-3 text-sm text-[--color-feedback-error]" role="alert">
          {error}
        </p>
      ) : null}

      {scoping && !review ? (
        <p className="text-sm text-[--color-text-secondary]">Scoping…</p>
      ) : null}

      {review ? (
        <>
          <div className="flex justify-between items-center mb-4">
            <p className="text-sm text-[--color-text-primary] font-medium">
              Connector readiness
            </p>
            <button
              type="button"
              onClick={onRescope}
              disabled={rescoping}
              className="text-xs px-3 py-1 rounded-[--radius-md] border border-[--color-border-subtle] text-[--color-text-secondary] hover:text-[--color-text-primary] disabled:opacity-50"
            >
              {rescoping ? "Re-scoping…" : "Re-scope all"}
            </button>
          </div>
          <div className="grid grid-cols-1 gap-3">
            {sortedDepartments.map((dept) => (
              <DepartmentCard key={dept.department_id} dept={dept} />
            ))}
          </div>
        </>
      ) : null}
    </WizardShell>
  );
}

function DepartmentCard({ dept }: { dept: ReviewDepartmentRow }) {
  const borderColor = dept.ready
    ? "var(--color-feedback-success)"
    : "var(--color-feedback-error)";
  const pillClass = dept.ready
    ? "bg-[--color-feedback-success]/15 text-[--color-feedback-success]"
    : "bg-[--color-feedback-error]/15 text-[--color-feedback-error]";
  const pillLabel = dept.ready ? "Ready" : "Not Ready";

  const byCategory = new Map<Category, ReviewCategoryRow>();
  for (const c of dept.categories) byCategory.set(c.category, c);
  const ordered = CATEGORY_ORDER.map((c) => byCategory.get(c)).filter(
    (c): c is ReviewCategoryRow => c !== undefined,
  );

  return (
    <article
      className="border border-[--color-border-subtle] rounded-[--radius-md] bg-[--color-bg-elevated] p-4"
      style={{ borderLeftWidth: 3, borderLeftColor: borderColor }}
    >
      <header className="flex justify-between gap-3 mb-2">
        <h4 className="text-sm font-semibold text-[--color-text-primary] capitalize">
          {dept.department_id.replace(/_/g, " ")}
        </h4>
        <span
          aria-label={`${dept.department_id} ${pillLabel}`}
          className={`text-xs px-2 py-0.5 rounded-full h-fit ${pillClass}`}
        >
          {pillLabel}
        </span>
      </header>
      <ul className="text-xs text-[--color-text-secondary] space-y-1">
        {ordered.map((c) => (
          <li key={c.category}>
            <CategoryLine row={c} />
          </li>
        ))}
      </ul>
    </article>
  );
}

function CategoryLine({ row }: { row: ReviewCategoryRow }) {
  const label = CATEGORY_LABEL[row.category];
  const providers = row.providers.join(", ");

  switch (row.status) {
    case "ok":
      return (
        <span className="text-[--color-feedback-success]">
          ✓ {label}: {row.tool_count} tools — {providers}
        </span>
      );
    case "missing":
      return (
        <span className="text-[--color-feedback-error]">
          ✗ {label}: 0 tools — add a {label} connector
        </span>
      );
    case "enhanced":
      return (
        <span>
          {label}: enhanced — {row.tool_count} tools
          {providers ? `, ${providers}` : ""}
        </span>
      );
    case "basic":
      return (
        <span className="text-[--color-text-tertiary]">
          {label}: basic — no connector
        </span>
      );
    default:
      return assertNever(row.status);
  }
}

function assertNever(_x: never): never {
  throw new Error("unreachable category status");
}
