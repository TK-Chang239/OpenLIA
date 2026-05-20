import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { CustomSection } from "../../api/equity-research";

interface Props {
  section: CustomSection;
  onChange: (next: CustomSection) => void;
  onRemove: () => void;
}

export function CustomSectionRow({ section, onChange, onRemove }: Props) {
  const { t } = useTranslation();
  return (
    <div className="flex items-start gap-2 py-2">
      <div className="flex-1 space-y-1">
        <input
          aria-label={t("equity_research.settings.custom_row_title_aria")}
          className="w-full rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 py-1 text-sm"
          value={section.title}
          onChange={(e) => onChange({ ...section, title: e.target.value })}
        />
        <textarea
          aria-label={t("equity_research.settings.custom_row_desc_aria")}
          rows={2}
          className="w-full rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 py-1 text-xs"
          value={section.description ?? ""}
          onChange={(e) =>
            onChange({ ...section, description: e.target.value || null })
          }
        />
      </div>
      <button
        type="button"
        aria-label={t("equity_research.settings.custom_row_remove_aria")}
        onClick={onRemove}
        className="p-1 text-[--color-text-tertiary] hover:text-[--color-text-primary]"
      >
        <X size={14} />
      </button>
    </div>
  );
}
