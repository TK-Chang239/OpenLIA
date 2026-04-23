interface Props {
  toolName: string;
  argsPreview: string;
  status: "running" | "done" | "failed";
  summary?: string;
}

export function ToolCallChip({ toolName, argsPreview, status, summary }: Props): JSX.Element {
  const label =
    status === "running" ? `${toolName}(${argsPreview})…` : (summary ?? `${toolName}(${argsPreview})`);
  const colorClass =
    status === "failed"
      ? "text-[--color-text-tertiary]"
      : "text-[--color-text-secondary]";
  return (
    <div
      className={`inline-flex max-w-full items-center gap-2 rounded-full border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-1 text-sm ${colorClass}`}
    >
      <span className="truncate">{label}</span>
    </div>
  );
}
