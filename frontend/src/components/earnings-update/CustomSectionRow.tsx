import { X } from "lucide-react";

import { CustomSection } from "../../api/earnings-update";

interface Props {
  value: CustomSection;
  onChange: (next: CustomSection) => void;
  onRemove: () => void;
}

export function CustomSectionRow({ value, onChange, onRemove }: Props) {
  return (
    <div className="flex items-start gap-2 p-2 border border-[--color-border-subtle] rounded-[--radius-md] mb-2">
      <div className="flex-1 flex flex-col gap-2">
        <input
          placeholder="Section title"
          value={value.title}
          onChange={(e) => onChange({ ...value, title: e.target.value })}
          className="bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-sm] px-2 h-8 text-sm"
        />
        <textarea
          placeholder="Description (optional — feeds the LLM)"
          value={value.description}
          onChange={(e) => onChange({ ...value, description: e.target.value })}
          className="bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-sm] px-2 py-1 text-sm min-h-[44px]"
        />
      </div>
      <button
        type="button"
        onClick={onRemove}
        aria-label="Remove custom section"
        className="p-1 text-[--color-text-tertiary] hover:text-[--color-feedback-error]"
      >
        <X size={14} />
      </button>
    </div>
  );
}
