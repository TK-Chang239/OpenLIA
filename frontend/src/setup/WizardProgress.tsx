export function WizardProgress({ value, max }: { value: number; max: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div
      role="progressbar"
      aria-label="Wizard progress"
      aria-valuenow={value}
      aria-valuemax={max}
      aria-valuemin={0}
      className="h-0.5 bg-border-subtle rounded-full"
    >
      <div
        className="h-full bg-accent-primary rounded-full transition-[width] duration-normal ease-out"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
