import { X } from "lucide-react";

import type { CustomSection } from "../../api/equity-research";

interface Props {
  section: CustomSection;
  onChange: (next: CustomSection) => void;
  onRemove: () => void;
}

export function CustomSectionRow({ section, onChange, onRemove }: Props) {
  return (
    <div className="flex items-start gap-2 py-2">
      <div className="flex-1 space-y-1">
        <input
          aria-label="Custom section title"
          className="w-full rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 py-1 text-sm"
          value={section.title}
          onChange={(e) => onChange({ ...section, title: e.target.value })}
        />
        <textarea
          aria-label="Custom section description"
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
        aria-label="Remove custom section"
        onClick={onRemove}
        className="p-1 text-[--color-text-tertiary] hover:text-[--color-text-primary]"
      >
        <X size={14} />
      </button>
    </div>
  );
}
