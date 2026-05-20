import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { CustomSection } from "../../api/earnings-update";

interface Props {
  value: CustomSection;
  onChange: (next: CustomSection) => void;
  onRemove: () => void;
}

export function CustomSectionRow({ value, onChange, onRemove }: Props) {
  const { t } = useTranslation();
  return (
    <div className="flex items-start gap-2 p-3 border border-[--color-border-subtle] rounded-md mb-2.5 bg-[--color-bg-elevated]">
      <div className="flex-1 flex flex-col gap-2">
        <input
          placeholder={t("earnings.custom_section.title_placeholder")}
          value={value.title}
          onChange={(e) => onChange({ ...value, title: e.target.value })}
          className="bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-md px-3 h-9 text-[13.5px] text-[--color-text-primary] outline-none focus:border-[--color-text-secondary] focus:shadow-[0_0_0_3px_rgba(var(--color-accent-primary-rgb),0.10)] transition-colors"
        />
        <textarea
          placeholder={t("earnings.custom_section.description_placeholder")}
          value={value.description}
          onChange={(e) => onChange({ ...value, description: e.target.value })}
          className="bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-md px-3 py-2 text-[13px] text-[--color-text-primary] min-h-[52px] outline-none focus:border-[--color-text-secondary] focus:shadow-[0_0_0_3px_rgba(var(--color-accent-primary-rgb),0.10)] transition-colors resize-y"
        />
      </div>
      <button
        type="button"
        onClick={onRemove}
        aria-label={t("earnings.custom_section.remove_aria")}
        className="p-1 mt-1 text-[--color-text-tertiary] hover:text-[--color-feedback-error] transition-colors"
      >
        <X size={14} />
      </button>
    </div>
  );
}
