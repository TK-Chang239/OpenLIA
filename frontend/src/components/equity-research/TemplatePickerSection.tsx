import * as Dialog from "@radix-ui/react-dialog";
import { Eye, FileText, Globe2, Pencil, Plus, Trash2, Upload, User, X } from "lucide-react";
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

const FORMAT_LABEL: Record<string, string> = {
  "text/markdown": "MD",
  "text/plain": "TXT",
  "application/json": "JSON",
  "application/pdf": "PDF",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
};

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

interface EditDraft {
  id: string;
  name: string;
  modes: Set<ReportMode>;
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
  const [editing, setEditing] = useState<EditDraft | null>(null);
  const [preview, setPreview] = useState<{ name: string; text: string } | null>(null);
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
      setTemplates((prev) =>
        prev.map((t) => (t.id === updated.id ? updated : t)),
      );
      setEditing(null);
    } catch (e) {
      setError((e as Error).message || "save failed");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (
      !window.confirm(
        "Delete this template? Anyone currently using it will revert to Default.",
      )
    ) {
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

  const defaultSelected = selectedId === "default" || !selectedId;

  return (
    <section
      className="border-b border-[--color-border-subtle] px-[22px] py-[18px]"
      aria-labelledby="er-template-section"
    >
      <div className="mb-[12px] flex items-center justify-between">
        <span
          id="er-template-section"
          className="block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]"
        >
          Report Template ·{" "}
          <strong className="font-medium text-[--color-text-primary]">
            {MODE_LABELS[mode]}
          </strong>
        </span>
        <span className="font-mono text-[10px] tracking-[0.08em] text-[--color-text-tertiary]">
          {compatible.length === 0
            ? "00"
            : String(compatible.length).padStart(2, "0")}
          <span className="opacity-60"> available</span>
        </span>
      </div>

      {error ? (
        <div
          role="alert"
          className="mb-[10px] flex items-start gap-[8px] rounded-md border border-[--color-feedback-danger] bg-[rgba(220,80,80,0.06)] px-[10px] py-[8px] text-[11.5px] leading-[1.45] text-[--color-feedback-danger]"
        >
          <span className="mt-[1px] font-mono text-[9px] uppercase tracking-[0.1em]">
            err
          </span>
          <span className="flex-1">{error}</span>
          <button
            type="button"
            onClick={() => setError(null)}
            aria-label="Dismiss error"
            className="text-[--color-feedback-danger] opacity-60 hover:opacity-100"
          >
            <X size={11} strokeWidth={2} />
          </button>
        </div>
      ) : null}

      <ul
        className="m-0 mt-1 flex list-none flex-col p-0"
        role="radiogroup"
        aria-label="Template choice"
      >
        <DefaultRow checked={defaultSelected} onSelect={() => onSelectedIdChange("default")} />

        {loading ? (
          <li className="flex items-center gap-2 border-t border-dashed border-[--color-border-subtle] py-[12px] font-mono text-[10.5px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
            <span className="inline-block h-1 w-1 animate-pulse rounded-full bg-[--color-text-tertiary]" />
            Loading templates
          </li>
        ) : compatible.length === 0 ? null : (
          compatible.map((t) => (
            <TemplateRow
              key={t.id}
              template={t}
              checked={selectedId === t.id}
              onSelect={() => onSelectedIdChange(t.id)}
              onPreview={() => openPreview(t)}
              onEdit={() => startEdit(t)}
              onDelete={() => handleDelete(t.id)}
              canMutate={t.owner_scope === "user" || isAdmin}
            />
          ))
        )}
      </ul>

      {draft ? (
        <UploadDraftCard
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
          className="mt-[12px] inline-flex h-7 items-center gap-[6px] rounded-md border border-dashed border-[--color-border-strong] bg-transparent px-[11px] font-display text-[12px] text-[--color-text-secondary] transition-all hover:border-solid hover:border-[--color-feedback-success] hover:bg-[rgba(212,255,0,0.05)] hover:text-[--color-feedback-success]"
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
        <EditDraftCard
          editing={editing}
          onChange={setEditing}
          onSubmit={submitEdit}
          onCancel={() => setEditing(null)}
          busy={busy}
        />
      ) : null}

      <PreviewDialog
        open={preview !== null}
        name={preview?.name ?? ""}
        text={preview?.text ?? ""}
        onClose={() => setPreview(null)}
      />
    </section>
  );
}

/* ───────────────────────────── default row ───────────────────────────── */

function DefaultRow({
  checked,
  onSelect,
}: {
  checked: boolean;
  onSelect: () => void;
}): JSX.Element {
  return (
    <li className="relative">
      {checked ? (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute left-0 top-[8px] bottom-[8px] w-[2px] rounded-r bg-[--color-accent-primary]"
        />
      ) : null}
      <button
        type="button"
        role="radio"
        aria-checked={checked}
        onClick={onSelect}
        className={[
          "group flex w-full items-center gap-[10px] rounded-md py-[10px] pl-[10px] pr-[8px] text-left transition-colors",
          checked ? "bg-[rgba(212,255,0,0.05)]" : "hover:bg-[--color-surface-hover]",
        ].join(" ")}
      >
        <RadioDot checked={checked} />
        <span className="flex-1 min-w-0">
          <span className="flex items-baseline gap-[8px]">
            <span className="text-[13.5px] font-medium text-[--color-text-primary]">
              Default
            </span>
            <span className="font-mono text-[9.5px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
              built-in framework
            </span>
          </span>
          <span className="mt-[2px] block text-[11.5px] leading-[1.4] text-[--color-text-tertiary]">
            Section toggles below apply.
          </span>
        </span>
      </button>
    </li>
  );
}

/* ───────────────────────────── template row ──────────────────────────── */

function TemplateRow({
  template: t,
  checked,
  onSelect,
  onPreview,
  onEdit,
  onDelete,
  canMutate,
}: {
  template: ErTemplate;
  checked: boolean;
  onSelect: () => void;
  onPreview: () => void;
  onEdit: () => void;
  onDelete: () => void;
  canMutate: boolean;
}): JSX.Element {
  const isGlobal = t.owner_scope === "global";
  const formatLabel = FORMAT_LABEL[t.raw_mime] ?? t.raw_mime.split("/").pop()?.toUpperCase() ?? "FILE";
  return (
    <li className="group/row relative border-t border-dashed border-[--color-border-subtle] first:border-t-0">
      {checked ? (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute left-0 top-[8px] bottom-[8px] w-[2px] rounded-r bg-[--color-accent-primary]"
        />
      ) : null}
      <div
        className={[
          "flex items-center gap-[10px] rounded-md py-[10px] pl-[10px] pr-[8px] transition-colors",
          checked ? "bg-[rgba(212,255,0,0.05)]" : "hover:bg-[--color-surface-hover]",
        ].join(" ")}
      >
        <button
          type="button"
          role="radio"
          aria-checked={checked}
          onClick={onSelect}
          className="flex flex-1 min-w-0 items-center gap-[10px] text-left"
        >
          <RadioDot checked={checked} />
          <span className="flex-1 min-w-0">
            <span className="flex items-baseline gap-[8px]">
              <span className="truncate text-[13.5px] font-medium text-[--color-text-primary]">
                {t.name}
              </span>
              <ScopeBadge global={isGlobal} />
            </span>
            <span className="mt-[3px] flex items-center gap-[8px] font-mono text-[10.5px] tracking-[0.04em] text-[--color-text-tertiary]">
              <FormatChip>{formatLabel}</FormatChip>
              <span className="text-[--color-text-secondary]">
                {`${t.estimated_tokens.toLocaleString()} tokens`}
              </span>
              <span aria-hidden="true" className="opacity-40">
                ·
              </span>
              <span className="truncate text-[--color-text-tertiary]">
                {t.raw_filename}
              </span>
            </span>
          </span>
        </button>
        <span
          className={[
            "flex items-center gap-[2px] transition-opacity",
            checked ? "opacity-100" : "opacity-0 group-hover/row:opacity-100 focus-within:opacity-100",
          ].join(" ")}
        >
          <IconButton title="Preview extracted text" onClick={onPreview}>
            <Eye size={12} />
          </IconButton>
          {canMutate ? (
            <>
              <IconButton title="Edit metadata" onClick={onEdit}>
                <Pencil size={12} />
              </IconButton>
              <IconButton title="Delete" onClick={onDelete}>
                <Trash2 size={12} />
              </IconButton>
            </>
          ) : null}
        </span>
      </div>
    </li>
  );
}

/* ───────────────────────────── primitives ────────────────────────────── */

function RadioDot({ checked }: { checked: boolean }): JSX.Element {
  return (
    <span
      aria-hidden="true"
      className={[
        "inline-flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full border-[1.5px] transition-colors",
        checked
          ? "border-[--color-accent-primary]"
          : "border-[--color-border-strong] group-hover/row:border-[--color-text-secondary]",
      ].join(" ")}
    >
      {checked ? (
        <span className="block h-[7px] w-[7px] rounded-full bg-[--color-accent-primary]" />
      ) : null}
    </span>
  );
}

function ScopeBadge({ global }: { global: boolean }): JSX.Element {
  const Icon = global ? Globe2 : User;
  return (
    <span
      className={[
        "inline-flex shrink-0 items-center gap-[3px] rounded-sm border px-[5px] py-[1px] font-mono text-[9px] uppercase tracking-[0.1em]",
        global
          ? "border-[--color-border-strong] bg-[--color-bg-base] text-[--color-text-secondary]"
          : "border-[--color-border-subtle] bg-transparent text-[--color-text-tertiary]",
      ].join(" ")}
    >
      <Icon size={9} strokeWidth={2.25} />
      {global ? "Global" : "Mine"}
    </span>
  );
}

function FormatChip({ children }: { children: string }): JSX.Element {
  return (
    <span className="inline-flex items-center rounded-sm border border-[--color-border-subtle] bg-[--color-bg-base] px-[5px] py-[1px] font-mono text-[9px] uppercase tracking-[0.1em] text-[--color-text-secondary]">
      {children}
    </span>
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
      className="inline-flex h-6 w-6 items-center justify-center rounded-md text-[--color-text-tertiary] transition-colors hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
    >
      {children}
    </button>
  );
}

/* ───────────────────────────── mode toggle chips ─────────────────────── */

function ModeChips({
  selected,
  onChange,
}: {
  selected: Set<ReportMode>;
  onChange: (next: Set<ReportMode>) => void;
}): JSX.Element {
  return (
    <div className="flex flex-wrap gap-[6px]">
      {ALL_MODES.map((m) => {
        const checked = selected.has(m);
        return (
          <button
            key={m}
            type="button"
            role="checkbox"
            aria-checked={checked}
            onClick={() => {
              const next = new Set(selected);
              if (checked) next.delete(m);
              else next.add(m);
              onChange(next);
            }}
            className={[
              "inline-flex h-[26px] items-center gap-[5px] rounded-md border px-[9px] font-display text-[11.5px] transition-colors",
              checked
                ? "border-[--color-accent-primary] bg-[rgba(212,255,0,0.10)] text-[--color-text-primary]"
                : "border-[--color-border-subtle] bg-transparent text-[--color-text-secondary] hover:border-[--color-border-strong] hover:text-[--color-text-primary]",
            ].join(" ")}
          >
            <span
              aria-hidden="true"
              className={[
                "inline-block h-[6px] w-[6px] rounded-full",
                checked ? "bg-[--color-accent-primary]" : "bg-[--color-border-strong]",
              ].join(" ")}
            />
            {MODE_LABELS[m]}
          </button>
        );
      })}
    </div>
  );
}

/* ───────────────────────────── upload form ───────────────────────────── */

function UploadDraftCard({
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
  const canSubmit = !busy && !!draft.file && !!draft.modes.size && !!draft.name.trim();
  return (
    <div className="mt-[12px] overflow-hidden rounded-md border border-[--color-border-subtle] bg-[--color-bg-base]">
      <div className="flex items-center gap-[8px] border-b border-[--color-border-subtle] px-[12px] py-[8px]">
        <span className="inline-flex h-[22px] w-[22px] items-center justify-center rounded-sm bg-[rgba(212,255,0,0.10)] text-[--color-feedback-success]">
          <Upload size={11} strokeWidth={2.25} />
        </span>
        <span className="flex-1 truncate text-[12px] text-[--color-text-primary]">
          <span className="font-mono text-[9.5px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
            file
          </span>{" "}
          <span className="font-medium">{draft.file?.name}</span>
        </span>
      </div>
      <div className="space-y-[14px] px-[12px] py-[12px]">
        <Field label="Name">
          <input
            aria-label="Template name"
            placeholder="Template name"
            className="h-[28px] w-full rounded-sm border border-[--color-border-subtle] bg-[--color-bg-input] px-[8px] text-[12.5px] text-[--color-text-primary] outline-none transition-colors focus:border-[--color-accent-primary]"
            value={draft.name}
            onChange={(e) => onChange({ ...draft, name: e.target.value })}
          />
        </Field>
        <Field label="Compatible modes">
          <ModeChips
            selected={draft.modes}
            onChange={(next) => onChange({ ...draft, modes: next })}
          />
        </Field>
        {isAdmin ? (
          <Field label="Scope">
            <ScopeToggle
              value={draft.scope}
              onChange={(s) => onChange({ ...draft, scope: s })}
            />
          </Field>
        ) : null}
        <div className="flex justify-end gap-[8px] pt-[2px]">
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex h-7 items-center rounded-md border border-[--color-border-subtle] bg-transparent px-[12px] font-display text-[12px] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onSubmit}
            disabled={!canSubmit}
            className="inline-flex h-7 items-center rounded-md bg-[--color-accent-primary] px-[12px] font-display text-[12px] font-medium text-[--color-accent-on] transition-colors hover:bg-[--color-accent-hover] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? "Uploading…" : "Save template"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ───────────────────────────── edit form ─────────────────────────────── */

function EditDraftCard({
  editing,
  onChange,
  onSubmit,
  onCancel,
  busy,
}: {
  editing: EditDraft;
  onChange: (next: EditDraft) => void;
  onSubmit: () => void;
  onCancel: () => void;
  busy: boolean;
}): JSX.Element {
  const canSubmit = !busy && !!editing.modes.size && !!editing.name.trim();
  return (
    <div className="mt-[12px] overflow-hidden rounded-md border border-[--color-border-subtle] bg-[--color-bg-base]">
      <div className="flex items-center gap-[8px] border-b border-[--color-border-subtle] px-[12px] py-[8px]">
        <span className="inline-flex h-[22px] w-[22px] items-center justify-center rounded-sm bg-[--color-surface-hover] text-[--color-text-secondary]">
          <Pencil size={11} strokeWidth={2.25} />
        </span>
        <span className="font-mono text-[9.5px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
          edit metadata
        </span>
      </div>
      <div className="space-y-[14px] px-[12px] py-[12px]">
        <Field label="Name">
          <input
            aria-label="Edit template name"
            className="h-[28px] w-full rounded-sm border border-[--color-border-subtle] bg-[--color-bg-input] px-[8px] text-[12.5px] text-[--color-text-primary] outline-none transition-colors focus:border-[--color-accent-primary]"
            value={editing.name}
            onChange={(e) => onChange({ ...editing, name: e.target.value })}
          />
        </Field>
        <Field label="Compatible modes">
          <ModeChips
            selected={editing.modes}
            onChange={(next) => onChange({ ...editing, modes: next })}
          />
        </Field>
        <div className="flex justify-end gap-[8px] pt-[2px]">
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex h-7 items-center rounded-md border border-[--color-border-subtle] bg-transparent px-[12px] font-display text-[12px] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onSubmit}
            disabled={!canSubmit}
            className="inline-flex h-7 items-center rounded-md bg-[--color-accent-primary] px-[12px] font-display text-[12px] font-medium text-[--color-accent-on] transition-colors hover:bg-[--color-accent-hover] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ───────────────────────────── form bits ─────────────────────────────── */

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <label className="block">
      <span className="mb-[6px] block font-mono text-[9.5px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
        {label}
      </span>
      {children}
    </label>
  );
}

function ScopeToggle({
  value,
  onChange,
}: {
  value: TemplateOwnerScope;
  onChange: (v: TemplateOwnerScope) => void;
}): JSX.Element {
  const options: { value: TemplateOwnerScope; label: string; sub: string }[] = [
    { value: "user", label: "Mine", sub: "Only you" },
    { value: "global", label: "Global (admin)", sub: "All users" },
  ];
  return (
    <div
      role="radiogroup"
      aria-label="Scope"
      className="flex gap-[2px] rounded-lg border border-[--color-border-subtle] bg-[--color-bg-elevated] p-[3px]"
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={[
              "flex-1 rounded-md px-[10px] py-[6px] text-left transition-colors",
              active
                ? "bg-[--color-bg-base] shadow-[0_1px_2px_rgba(13,13,11,0.06)]"
                : "hover:bg-[--color-surface-hover]",
            ].join(" ")}
          >
            <span className="block font-display text-[12px] font-medium text-[--color-text-primary]">
              {opt.label}
            </span>
            <span className="block font-mono text-[9.5px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
              {opt.sub}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/* ───────────────────────────── preview dialog ────────────────────────── */

function PreviewDialog({
  open,
  name,
  text,
  onClose,
}: {
  open: boolean;
  name: string;
  text: string;
  onClose: () => void;
}): JSX.Element {
  const lineCount = useMemo(
    () => (text ? text.split("\n").length : 0),
    [text],
  );
  const charCount = text.length;
  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[60] bg-[rgba(13,13,11,0.55)]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-[60] flex max-h-[82vh] w-full max-w-[680px] -translate-x-1/2 -translate-y-1/2 flex-col rounded-[14px] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-[0_16px_40px_rgba(13,13,11,0.18)]">
          <div className="flex items-center gap-[10px] border-b border-[--color-border-subtle] px-[22px] py-[16px]">
            <span className="inline-flex h-[26px] w-[26px] items-center justify-center rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] text-[--color-text-secondary]">
              <FileText size={13} strokeWidth={1.9} />
            </span>
            <div className="flex min-w-0 flex-1 flex-col">
              <Dialog.Title className="m-0 truncate text-[14px] font-semibold tracking-[-0.005em] text-[--color-text-primary]">
                {name || "Preview"}
              </Dialog.Title>
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                extracted text · {lineCount.toLocaleString()} lines ·{" "}
                {charCount.toLocaleString()} chars
              </span>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close preview"
              className="ml-auto inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
            >
              <X size={14} strokeWidth={2} />
            </button>
          </div>
          <div className="flex-1 overflow-auto bg-[--color-bg-base]">
            <pre className="m-0 whitespace-pre-wrap px-[22px] py-[18px] font-mono text-[11.5px] leading-[1.55] text-[--color-text-primary]">
              {text}
            </pre>
          </div>
          <div className="flex items-center justify-between gap-[10px] rounded-b-[14px] border-t border-[--color-border-subtle] bg-[--color-bg-base] px-[22px] py-[12px]">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
              read-only · this is what the model sees
            </span>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-7 items-center rounded-md border border-[--color-border-subtle] bg-transparent px-[12px] font-display text-[12px] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
            >
              Close
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
