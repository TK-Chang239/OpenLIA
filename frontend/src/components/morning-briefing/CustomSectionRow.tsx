import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { CustomSection } from "../../api/morning-briefing";

interface Props {
  section: CustomSection;
  onChange: (patch: Partial<CustomSection>) => void;
  onRemove: () => void;
}

export function CustomSectionRow({ section, onChange, onRemove }: Props) {
  const { t } = useTranslation();
  return (
    <article
      className="bg-[--color-bg-elevated] border rounded-[--radius-lg] p-4 px-5"
      style={{ borderColor: "var(--color-border-subtle)" }}
      data-testid={`custom-section-row-${section.id}`}
    >
      <div className="flex justify-between items-start gap-3">
        <div className="flex-1 min-w-0 flex flex-col gap-2">
          <input
            placeholder={t("morning_briefing.custom_section.title_placeholder")}
            value={section.title}
            onChange={(e) => onChange({ title: e.target.value })}
            data-testid={`custom-section-title-${section.id}`}
            className="h-[34px] w-full rounded-md border bg-[--color-bg-input] px-2.5 text-[14px] font-medium text-[--color-text-primary] outline-none focus:border-[--color-accent-primary] placeholder:text-[--color-text-tertiary]"
            style={{ borderColor: "var(--color-border-subtle)" }}
          />
          <textarea
            placeholder={t("morning_briefing.custom_section.description_placeholder")}
            value={section.description}
            onChange={(e) => onChange({ description: e.target.value })}
            data-testid={`custom-section-description-${section.id}`}
            className="h-16 w-full rounded-md border bg-[--color-bg-input] px-2.5 py-2 text-[13px] leading-[1.5] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary] placeholder:text-[--color-text-tertiary] resize-y"
            style={{ borderColor: "var(--color-border-subtle)" }}
          />
        </div>
        <button
          type="button"
          aria-label={t("morning_briefing.custom_section.remove_aria")}
          onClick={onRemove}
          data-testid={`custom-section-remove-${section.id}`}
          className="inline-flex items-center justify-center h-7 w-7 rounded-md text-[--color-feedback-error] hover:bg-[rgba(224,92,48,0.08)]"
        >
          <X size={14} strokeWidth={1.8} />
        </button>
      </div>
    </article>
  );
}
