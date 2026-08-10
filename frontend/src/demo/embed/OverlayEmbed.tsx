import { MockupEmbed } from "./MockupEmbed";

// Full-screen overlay that embeds a sub-screen mockup (a report, a library, a
// schedules view) with a Close button. Used by the adopted department pages.
export function OverlayEmbed({
  url,
  label,
  onClose,
}: {
  url: string;
  label: string;
  onClose: () => void;
}): JSX.Element {
  return (
    <div
      className="fixed inset-0 z-[1000] flex flex-col bg-[--color-bg-base]"
      role="dialog"
      aria-label={label}
    >
      <button
        type="button"
        onClick={onClose}
        className="absolute right-4 top-4 z-10 rounded-md border border-[--color-border-strong] bg-[--color-bg-elevated] px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.08em] text-[--color-text-primary] hover:bg-[--color-surface-hover]"
      >
        Close
      </button>
      <MockupEmbed url={url} />
    </div>
  );
}
