import { Eye, Pencil, Plus, Trash2 } from "lucide-react";
import { type JSX, useEffect, useMemo, useRef, useState } from "react";

import {
  type ErTemplate,
  type ReportMode,
  type TemplateOwnerScope,
  deleteErTemplate,
  fetchErTemplateExtractedText,
  listErTemplates,
  patchErTemplate,
  uploadErTemplate,
} from "../../api/equity-research";

const MODE_LABELS: Record<ReportMode, string> = {
  stock_initiation: "Stock Initiation",
  stock_update: "Stock Update",
  sector_research: "Sector Research",
};

const ALL_MODES: ReportMode[] = [
  "stock_initiation",
  "stock_update",
  "sector_research",
];

interface Props {
  mode: ReportMode;
  selectedId: string;
  onSelectedIdChange: (id: string) => void;
  isAdmin: boolean;
}

interface UploadDraft {
  file: File | null;
  name: string;
  modes: Set<ReportMode>;
  scope: TemplateOwnerScope;
}

export function TemplatePickerSection({
  mode,
  selectedId,
  onSelectedIdChange,
  isAdmin,
}: Props): JSX.Element {
  const [templates, setTemplates] = useState<ErTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<UploadDraft | null>(null);
  const [editing, setEditing] = useState<{
    id: string;
    name: string;
    modes: Set<ReportMode>;
  } | null>(null);
  const [preview, setPreview] = useState<{ name: string; text: string } | null>(
    null,
  );
  const [busy, setBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listErTemplates()
      .then((rows) => {
        if (!cancelled) setTemplates(rows);
      })
      .catch((e) => {
        if (!cancelled) setError((e as Error).message || "load failed");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const compatible = useMemo(
    () => templates.filter((t) => t.compatible_modes.includes(mode)),
    [templates, mode],
  );

  const handleFileSelected = (file: File) => {
    const stripped = file.name.replace(/\.[^.]+$/, "");
    setDraft({
      file,
      name: stripped || "template",
      modes: new Set([mode]),
      scope: "user",
    });
  };

  const submitUpload = async () => {
    if (!draft || !draft.file) return;
    setBusy(true);
    setError(null);
    try {
      const created = await uploadErTemplate({
        file: draft.file,
        name: draft.name,
        compatibleModes: Array.from(draft.modes),
        scope: draft.scope,
      });
      setTemplates((prev) => [...prev, created]);
      setDraft(null);
    } catch (e) {
      setError((e as Error).message || "upload failed");
    } finally {
      setBusy(false);
    }
  };

  const startEdit = (t: ErTemplate) => {
    setEditing({
      id: t.id,
      name: t.name,
      modes: new Set(t.compatible_modes),
    });
  };

  const submitEdit = async () => {
    if (!editing) return;
    setBusy(true);
    try {
      const updated = await patchErTemplate(editing.id, {
        name: editing.name,
        compatible_modes: Array.from(editing.modes),
      });
      setTemplates((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      setEditing(null);
    } catch (e) {
      setError((e as Error).message || "save failed");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Delete this template? Anyone using it will revert to Default.")) {
      return;
    }
    setBusy(true);
    try {
      await deleteErTemplate(id);
      setTemplates((prev) => prev.filter((t) => t.id !== id));
      if (selectedId === id) onSelectedIdChange("default");
    } catch (e) {
      setError((e as Error).message || "delete failed");
    } finally {
      setBusy(false);
    }
  };

  const openPreview = async (t: ErTemplate) => {
    try {
      const text = await fetchErTemplateExtractedText(t.id);
      setPreview({ name: t.name, text });
    } catch (e) {
      setError((e as Error).message || "preview failed");
    }
  };

  return (
    <section
      className="border-b border-[--color-border-subtle] px-[22px] py-[18px]"
      aria-labelledby="er-template-section"
    >
      <span
        id="er-template-section"
        className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]"
      >
        Report Template · <strong className="font-medium text-[--color-text-primary]">{MODE_LABELS[mode]}</strong>
      </span>

      {error ? (
        <div className="mb-2 rounded border border-[--color-feedback-danger] bg-[rgba(255,80,80,0.06)] px-2 py-1 text-xs text-[--color-feedback-danger]">
          {error}
        </div>
      ) : null}

      <ul className="m-0 mt-1 flex list-none flex-col p-0" role="radiogroup" aria-label="Template choice">
        <TemplateOption
          checked={selectedId === "default" || !selectedId}
          onSelect={() => onSelectedIdChange("default")}
          label="Default"
          sublabel="Built-in framework · section toggles below apply"
          badge={null}
        />
        {loading ? (
          <li className="py-2 text-xs text-[--color-text-tertiary]">Loading templates…</li>
        ) : (
          compatible.map((t) => (
            <TemplateOption
              key={t.id}
              checked={selectedId === t.id}
              onSelect={() => onSelectedIdChange(t.id)}
              label={t.name}
              sublabel={`${t.estimated_tokens.toLocaleString()} tokens · ${t.raw_filename}`}
              badge={t.owner_scope === "global" ? "Global" : "Mine"}
              actions={
                <span className="flex items-center gap-1">
                  <IconButton title="Preview extracted text" onClick={() => openPreview(t)}>
                    <Eye size={12} />
                  </IconButton>
                  {(t.owner_scope === "user" || isAdmin) && (
                    <>
                      <IconButton title="Edit metadata" onClick={() => startEdit(t)}>
                        <Pencil size={12} />
                      </IconButton>
                      <IconButton title="Delete" onClick={() => handleDelete(t.id)}>
                        <Trash2 size={12} />
                      </IconButton>
                    </>
                  )}
                </span>
              }
            />
          ))
        )}
      </ul>

      {draft ? (
        <UploadDraftRow
          draft={draft}
          isAdmin={isAdmin}
          onChange={setDraft}
          onSubmit={submitUpload}
          onCancel={() => setDraft(null)}
          busy={busy}
        />
      ) : (
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="mt-2 inline-flex h-7 items-center gap-[6px] rounded-md border border-dashed border-[--color-border-strong] bg-transparent px-[11px] font-display text-[12px] text-[--color-text-secondary] transition-all hover:border-solid hover:border-[--color-feedback-success] hover:bg-[rgba(212,255,0,0.05)] hover:text-[--color-feedback-success]"
        >
          <Plus size={11} strokeWidth={2} />
          Add template
        </button>
      )}
      <input
        ref={fileInputRef}
        type="file"
        accept=".md,.markdown,.txt,.json,.pdf,.docx"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleFileSelected(f);
          e.target.value = "";
        }}
      />

      {editing ? (
        <EditDraftRow
          editing={editing}
          onChange={setEditing}
          onSubmit={submitEdit}
          onCancel={() => setEditing(null)}
          busy={busy}
        />
      ) : null}

      {preview ? (
        <PreviewModal
          name={preview.name}
          text={preview.text}
          onClose={() => setPreview(null)}
        />
      ) : null}
    </section>
  );
}

interface OptionProps {
  checked: boolean;
  onSelect: () => void;
  label: string;
  sublabel: string;
  badge: string | null;
  actions?: JSX.Element;
}

function TemplateOption({ checked, onSelect, label, sublabel, badge, actions }: OptionProps): JSX.Element {
  return (
    <li className="flex items-center gap-[10px] border-b border-dashed border-[--color-border-subtle] py-[9px] last:border-b-0">
      <button
        type="button"
        role="radio"
        aria-checked={checked}
        onClick={onSelect}
        className="flex flex-1 items-center gap-[10px] text-left"
      >
        <span
          aria-hidden="true"
          className={[
            "inline-flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full border-[1.5px]",
            checked ? "border-[--color-accent-primary]" : "border-[--color-border-strong]",
          ].join(" ")}
        >
          {checked ? (
            <span className="block h-2 w-2 rounded-full bg-[--color-accent-primary]" />
          ) : null}
        </span>
        <span className="flex-1">
          <span className="block text-[13.5px] text-[--color-text-primary]">{label}</span>
          <span className="block text-[11px] text-[--color-text-tertiary]">{sublabel}</span>
        </span>
        {badge ? (
          <span className="rounded-sm border border-[--color-border-subtle] px-1.5 py-0.5 font-mono text-[9.5px] uppercase tracking-[0.08em] text-[--color-text-secondary]">
            {badge}
          </span>
        ) : null}
      </button>
      {actions}
    </li>
  );
}

function IconButton({
  children,
  onClick,
  title,
}: {
  children: JSX.Element;
  onClick: () => void;
  title: string;
}): JSX.Element {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className="inline-flex h-6 w-6 items-center justify-center rounded-md text-[--color-text-tertiary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
    >
      {children}
    </button>
  );
}

function ModeCheckboxes({
  selected,
  onChange,
}: {
  selected: Set<ReportMode>;
  onChange: (next: Set<ReportMode>) => void;
}): JSX.Element {
  return (
    <div className="flex flex-wrap gap-2 text-xs">
      {ALL_MODES.map((m) => {
        const checked = selected.has(m);
        return (
          <label key={m} className="inline-flex cursor-pointer items-center gap-1">
            <input
              type="checkbox"
              checked={checked}
              onChange={() => {
                const next = new Set(selected);
                if (checked) next.delete(m);
                else next.add(m);
                onChange(next);
              }}
            />
            <span>{MODE_LABELS[m]}</span>
          </label>
        );
      })}
    </div>
  );
}

function UploadDraftRow({
  draft,
  isAdmin,
  onChange,
  onSubmit,
  onCancel,
  busy,
}: {
  draft: UploadDraft;
  isAdmin: boolean;
  onChange: (next: UploadDraft) => void;
  onSubmit: () => void;
  onCancel: () => void;
  busy: boolean;
}): JSX.Element {
  return (
    <div className="mt-3 space-y-2 rounded-md border border-[--color-border-subtle] p-2">
      <div className="text-xs text-[--color-text-tertiary]">
        File: <strong className="text-[--color-text-primary]">{draft.file?.name}</strong>
      </div>
      <input
        aria-label="Template name"
        placeholder="Name"
        className="w-full rounded-sm border border-[--color-border-subtle] bg-[--color-bg-input] px-2 py-1 text-sm"
        value={draft.name}
        onChange={(e) => onChange({ ...draft, name: e.target.value })}
      />
      <ModeCheckboxes
        selected={draft.modes}
        onChange={(next) => onChange({ ...draft, modes: next })}
      />
      {isAdmin ? (
        <div className="flex gap-3 text-xs">
          {(["user", "global"] as TemplateOwnerScope[]).map((s) => (
            <label key={s} className="inline-flex cursor-pointer items-center gap-1">
              <input
                type="radio"
                name="upload-scope"
                checked={draft.scope === s}
                onChange={() => onChange({ ...draft, scope: s })}
              />
              <span>{s === "user" ? "My template" : "Global (admin)"}</span>
            </label>
          ))}
        </div>
      ) : null}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="h-7 px-2 text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={busy || !draft.modes.size || !draft.name}
          className="h-7 rounded-sm bg-[--color-accent-primary] px-2 text-sm text-[--color-accent-on] disabled:opacity-40"
        >
          {busy ? "Uploading…" : "Save template"}
        </button>
      </div>
    </div>
  );
}

function EditDraftRow({
  editing,
  onChange,
  onSubmit,
  onCancel,
  busy,
}: {
  editing: { id: string; name: string; modes: Set<ReportMode> };
  onChange: (next: { id: string; name: string; modes: Set<ReportMode> }) => void;
  onSubmit: () => void;
  onCancel: () => void;
  busy: boolean;
}): JSX.Element {
  return (
    <div className="mt-3 space-y-2 rounded-md border border-[--color-border-subtle] p-2">
      <input
        aria-label="Edit template name"
        className="w-full rounded-sm border border-[--color-border-subtle] bg-[--color-bg-input] px-2 py-1 text-sm"
        value={editing.name}
        onChange={(e) => onChange({ ...editing, name: e.target.value })}
      />
      <ModeCheckboxes
        selected={editing.modes}
        onChange={(next) => onChange({ ...editing, modes: next })}
      />
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="h-7 px-2 text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={busy || !editing.modes.size || !editing.name}
          className="h-7 rounded-sm bg-[--color-accent-primary] px-2 text-sm text-[--color-accent-on] disabled:opacity-40"
        >
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}

function PreviewModal({
  name,
  text,
  onClose,
}: {
  name: string;
  text: string;
  onClose: () => void;
}): JSX.Element {
  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[rgba(13,13,11,0.55)]"
      onClick={onClose}
    >
      <div
        className="flex max-h-[80vh] w-[640px] flex-col rounded-[14px] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-[0_16px_40px_rgba(13,13,11,0.18)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center border-b border-[--color-border-subtle] px-[18px] py-[12px]">
          <span className="text-[14px] font-semibold text-[--color-text-primary]">{name}</span>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
          >
            Close
          </button>
        </div>
        <pre className="m-0 flex-1 overflow-auto whitespace-pre-wrap px-[18px] py-[14px] font-mono text-[11.5px] leading-[1.5] text-[--color-text-primary]">
          {text}
        </pre>
      </div>
    </div>
  );
}
