/**
 * SkipBannerBlock — renders a v2.2 `skip_banner` block.
 *
 * Emitted by the v2.2 pipeline when a section's `trigger_when` condition
 * evaluates to false. The card communicates that the section was
 * deliberately not generated, with the trigger reason.
 */
export interface SkipBannerBlockProps {
  type: "skip_banner";
  section_name: string;
  reason: string;
}

export function SkipBannerBlock({ section_name, reason }: SkipBannerBlockProps) {
  return (
    <div
      role="note"
      className="my-3 rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-4 py-3"
      data-block-type="skip_banner"
    >
      <p className="m-0 font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
        Section skipped
      </p>
      <p className="m-0 mt-1 text-[13px] font-medium text-[--color-text-primary]">
        {section_name}
      </p>
      <p className="m-0 mt-1 text-[12.5px] leading-[1.5] text-[--color-text-secondary]">
        {reason}
      </p>
    </div>
  );
}
