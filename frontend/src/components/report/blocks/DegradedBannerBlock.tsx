/**
 * DegradedBannerBlock — renders a v2.2 `degraded_banner` block.
 *
 * Emitted when the verifier could not raise a section's quality enough
 * after the retry budget. Marks the section as degraded with a list of
 * issues left open.
 */
export interface DegradedBannerBlockProps {
  type: "degraded_banner";
  section_name: string;
  reason: string;
  issue_list?: string[];
}

export function DegradedBannerBlock({
  section_name,
  reason,
  issue_list,
}: DegradedBannerBlockProps) {
  return (
    <div
      role="alert"
      className="my-3 rounded-md border border-[--color-feedback-warning] bg-[rgba(245,158,11,0.08)] px-4 py-3"
      data-block-type="degraded_banner"
    >
      <p className="m-0 font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-feedback-warning]">
        Section degraded
      </p>
      <p className="m-0 mt-1 text-[13px] font-medium text-[--color-text-primary]">
        {section_name}
      </p>
      <p className="m-0 mt-1 text-[12.5px] leading-[1.5] text-[--color-text-secondary]">
        {reason}
      </p>
      {issue_list && issue_list.length > 0 ? (
        <ul className="m-0 mt-2 list-disc pl-5 text-[12px] text-[--color-text-tertiary]">
          {issue_list.map((it) => (
            <li key={it}>{it}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
