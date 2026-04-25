import type { CustomSection } from "../../api/morning-briefing";

interface Props {
  section: CustomSection;
  onChange: (patch: Partial<CustomSection>) => void;
  onRemove: () => void;
}

export function CustomSectionRow({ section, onChange, onRemove }: Props) {
  return (
    <div
      className="rounded-[var(--radius-lg,0.5rem)] border p-3 space-y-2"
      style={{
        borderColor: "var(--color-border-subtle)",
        background: "var(--color-bg-base)",
      }}
      data-testid={`custom-section-row-${section.id}`}
    >
      <div className="flex items-center gap-2">
        <input
          className="flex-1 rounded border px-2 py-1 text-sm"
          style={{ borderColor: "var(--color-border-subtle)" }}
          placeholder="Section title"
          value={section.title}
          onChange={(e) => onChange({ title: e.target.value })}
          data-testid={`custom-section-title-${section.id}`}
        />
        <button
          type="button"
          aria-label="Remove section"
          onClick={onRemove}
          className="text-base px-2"
          style={{ color: "var(--color-text-tertiary)" }}
          data-testid={`custom-section-remove-${section.id}`}
        >
          {"×"}
        </button>
      </div>
      <textarea
        className="w-full rounded border px-2 py-1 text-sm"
        style={{ borderColor: "var(--color-border-subtle)" }}
        placeholder="Description — tells the LLM what this section covers"
        value={section.description}
        onChange={(e) => onChange({ description: e.target.value })}
        data-testid={`custom-section-description-${section.id}`}
      />
    </div>
  );
}
