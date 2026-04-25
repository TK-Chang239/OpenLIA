import { useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { ProviderRow } from "./ProviderRow";
import { AddProviderForm } from "./AddProviderForm";
import { confirmProviders, deleteProvider, listProviders } from "../../api/setup";
import type { ProviderRow as Row } from "../../api/setup";

type Category = "financial" | "news" | "social" | "web_search";
const CATEGORIES: { value: Category; label: string; required?: boolean }[] = [
  { value: "financial", label: "Financial", required: true },
  { value: "news", label: "News", required: true },
  { value: "social", label: "Social" },
  { value: "web_search", label: "Web Search" },
];

export function ProvidersStep({
  totalSteps,
  onBack,
  onSaved,
}: {
  totalSteps: number;
  onBack: () => void;
  onSaved: () => void;
}) {
  const [active, setActive] = useState<Category>("financial");
  const [rows, setRows] = useState<Row[]>([]);
  const [adding, setAdding] = useState(false);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    const resp = await listProviders();
    setRows(resp.providers);
  };

  useEffect(() => {
    void refresh();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const byCategory = useMemo(() => {
    const out: Record<Category, Row[]> = { financial: [], news: [], social: [], web_search: [] };
    for (const r of rows) out[r.category as Category]?.push(r);
    return out;
  }, [rows]);

  const canAdvance =
    byCategory.financial.some((r) => r.status === "ok") &&
    byCategory.news.some((r) => r.status === "ok");

  const onNext = async () => {
    setLoading(true);
    try {
      await confirmProviders();
      onSaved();
    } finally {
      setLoading(false);
    }
  };

  return (
    <WizardShell
      title="Data Providers"
      stepIndex={3}
      totalSteps={totalSteps}
      footer={
        <WizardFooter onBack={onBack} onNext={onNext} nextDisabled={!canAdvance} loading={loading} />
      }
    >
      <div className="flex gap-6">
        <nav role="tablist" aria-label="Provider categories" className="w-44 flex-shrink-0">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.value}
              role="tab"
              aria-label={cat.label}
              aria-selected={active === cat.value}
              onClick={() => {
                setActive(cat.value);
                setAdding(false);
              }}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-[--radius-md] text-sm cursor-pointer ${
                active === cat.value
                  ? "bg-[--color-surface-active] text-[--color-text-primary] font-medium"
                  : "text-[--color-text-secondary] hover:bg-[--color-surface-hover]"
              }`}
            >
              <span>
                {cat.label}
                {cat.required ? " *" : ""}
              </span>
              <span className="text-[10px] px-1.5 py-0.5 bg-[--color-surface-hover] rounded-full text-[--color-text-tertiary]">
                {byCategory[cat.value].length}
              </span>
            </button>
          ))}
        </nav>
        <section role="tabpanel" aria-label={active} className="flex-1 min-w-0">
          {adding ? (
            <AddProviderForm
              category={active}
              onCancel={() => setAdding(false)}
              onSaved={async () => {
                setAdding(false);
                await refresh();
              }}
            />
          ) : (
            <>
              <ul className="flex flex-col">
                {byCategory[active].map((r, i) => (
                  <ProviderRow
                    key={r.id}
                    row={r}
                    priorityIndex={i}
                    onRemove={async () => {
                      await deleteProvider(r.id);
                      await refresh();
                    }}
                  />
                ))}
              </ul>
              <button
                type="button"
                onClick={() => setAdding(true)}
                className="inline-flex items-center gap-2 h-8 px-3 rounded-[--radius-md] border border-dashed border-[--color-border-secondary] text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
              >
                <Plus size={14} />
                Add {active.replace("_", " ")} provider
              </button>
            </>
          )}
        </section>
      </div>
    </WizardShell>
  );
}
