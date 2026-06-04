/**
 * SignalAlert — renders a signal notification card.
 * Used by the RS overview view for the signals list.
 */
interface SignalProps {
  name: string;
  severity: "info" | "caution" | "alert";
  note: string;
}

export function SignalAlert({ name, severity, note }: SignalProps) {
  const tone =
    severity === "alert"
      ? "var(--color-feedback-error)"
      : severity === "caution"
        ? "var(--color-feedback-warning)"
        : "var(--color-text-secondary)";
  const label = severity.toUpperCase();

  return (
    <div
      data-testid={`signal-${severity}`}
      className="rs-col-card text-left p-4 w-full"
      style={{ borderRadius: "10px", borderColor: tone }}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2">
          <span
            className="rs-mono-label"
            style={{ color: tone, letterSpacing: "0.16em" }}
          >
            {label}
          </span>
          <span
            className="font-mono font-semibold tracking-[0.02em] text-[--color-text-primary]"
            style={{ fontSize: "14px" }}
          >
            {name}
          </span>
        </span>
      </div>
      <div className="rs-mono-label mt-2 text-[--color-text-secondary]">{note}</div>
    </div>
  );
}
