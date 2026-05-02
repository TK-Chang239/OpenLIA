import type { BuiltinTemplate } from "../../api/connectors";

interface Props {
  template: BuiltinTemplate;
  onClick: () => void;
}

export function CatalogCard({ template, onClick }: Props) {
  const needCount = template.covered_need_ids.length;
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-lg border border-border-subtle p-4 text-left hover:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary"
    >
      <div className="flex items-center justify-between">
        <span className="font-semibold text-text-primary">
          {template.display_name}
        </span>
        <span className="rounded bg-surface-hover px-2 py-0.5 text-xs uppercase text-text-secondary">
          {template.category}
        </span>
      </div>
      <p className="mt-2 text-sm text-text-secondary">
        {needCount > 0
          ? `Covers ${needCount} runner need${needCount === 1 ? "" : "s"}.`
          : "Chat tools only."}
      </p>
    </button>
  );
}
