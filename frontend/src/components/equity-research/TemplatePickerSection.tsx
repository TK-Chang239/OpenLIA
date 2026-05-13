import * as Dialog from "@radix-ui/react-dialog";
import {
  Check,
  ChevronLeft,
  Download,
  Eye,
  FileText,
  LayoutGrid,
  Pencil,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { type JSX, useEffect, useMemo, useRef, useState } from "react";

import {
  type ErTemplate,
  type ReportMode,
  type TemplateOwnerScope,
  deleteErTemplate,
  erTemplateRawUrl,
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

const MODE_SUBLABELS: Record<ReportMode, string> = {
  stock_initiation: "Full coverage initiation report",
  stock_update: "Post-event or earnings update",
  sector_research: "Industry-wide thematic report",
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
  onActiveTemplateChange?: (t: ErTemplate | null) => void;
}

interface UploadDraft {
  file: File;
  name: string;
  modes: Set<ReportMode>;
  scope: TemplateOwnerScope;
}

interface EditDraft {
  id: string;
  filename: string;
  filesize: number;
  format: string;
  name: string;
  modes: Set<ReportMode>;
}

type View = { kind: "list" } | { kind: "upload" } | { kind: "edit" };

export function TemplatePickerSection({
  mode,
  selectedId,
  onSelectedIdChange,
  isAdmin,
  onActiveTemplateChange,
}: Props): JSX.Element {
  const [templates, setTemplates] = useState<ErTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>({ kind: "list" });
  const [draft, setDraft] = useState<UploadDraft | null>(null);
  const [editing, setEditing] = useState<EditDraft | null>(null);
  const [preview, setPreview] = useState<{ name: string; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [modesError, setModesError] = useState(false);
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

  const defaultSelected = selectedId === "default" || !selectedId;
  const activeTemplate = !defaultSelected
    ? templates.find((t) => t.id === selectedId) ?? null
    : null;

  useEffect(() => {
    onActiveTemplateChange?.(activeTemplate);
  }, [activeTemplate, onActiveTemplateChange]);

  /* ───────────────── handlers ───────────────── */

  const handleFileSelected = (file: File) => {
    const stripped = file.name.replace(/\.[^.]+$/, "");
    setDraft({
      file,
      name: stripped || "template",
      modes: new Set([mode]),
      scope: "user",
    });
    setModesError(false);
    setView({ kind: "upload" });
  };

  const submitUpload = async () => {
    if (!draft) return;
    if (draft.modes.size === 0) {
      setModesError(true);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await uploadErTemplate({
        file: draft.file,
        name: draft.name.trim() || draft.file.name,
        compatibleModes: Array.from(draft.modes),
        scope: draft.scope,
      });
      setTemplates((prev) => [...prev, created]);
      setDraft(null);
      setView({ kind: "list" });
    } catch (e) {
      setError((e as Error).message || "upload failed");
    } finally {
      setBusy(false);
    }
  };

  const startEdit = (t: ErTemplate) => {
    setEditing({
      id: t.id,
      filename: t.raw_filename,
      filesize: t.raw_size_bytes,
      format: FORMAT_LABEL[t.raw_mime] ?? "FILE",
      name: t.name,
      modes: new Set(t.compatible_modes),
    });
    setModesError(false);
    setView({ kind: "edit" });
  };

  const submitEdit = async () => {
    if (!editing) return;
    if (editing.modes.size === 0) {
      setModesError(true);
      return;
    }
    setBusy(true);
    try {
      const updated = await patchErTemplate(editing.id, {
        name: editing.name.trim() || editing.filename,
        compatible_modes: Array.from(editing.modes),
      });
      setTemplates((prev) =>
        prev.map((t) => (t.id === updated.id ? updated : t)),
      );
      setEditing(null);
      setView({ kind: "list" });
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

  const cancelConfig = () => {
    setDraft(null);
    setEditing(null);
    setView({ kind: "list" });
    setModesError(false);
  };

  /* ───────────────── render ───────────────── */

  return (
    <section
      className="border-b border-[--color-border-subtle] px-[22px] py-[18px]"
      aria-labelledby="er-template-section"
    >
      <div className="mb-[10px] flex items-center justify-between gap-[10px]">
        <span
          id="er-template-section"
          className="block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]"
        >
          Report Template ·{" "}
          <strong className="font-medium normal-case tracking-normal text-[--color-text-primary]">
            {MODE_LABELS[mode]}
          </strong>
        </span>
        {view.kind === "list" ? (
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="inline-flex h-[28px] items-center gap-[6px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-[11px] font-display text-[12px] text-[--color-text-secondary] transition-colors hover:border-[--color-border-strong] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
          >
            <Upload size={12} strokeWidth={2} />
            Upload template
          </button>
        ) : null}
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

      {view.kind === "list" ? (
        <ListView
          loading={loading}
          compatible={compatible}
          activeTemplate={activeTemplate}
          defaultSelected={defaultSelected}
          selectedId={selectedId}
          isAdmin={isAdmin}
          onSelect={onSelectedIdChange}
          onPreview={openPreview}
          onEdit={startEdit}
          onDelete={handleDelete}
          onUploadClick={() => fileInputRef.current?.click()}
        />
      ) : null}

      {view.kind === "upload" && draft ? (
        <ConfigureView
          kind="upload"
          isAdmin={isAdmin}
          draft={draft}
          onDraftChange={(d) => setDraft(d)}
          modesError={modesError}
          onSubmit={submitUpload}
          onCancel={cancelConfig}
          busy={busy}
        />
      ) : null}

      {view.kind === "edit" && editing ? (
        <ConfigureView
          kind="edit"
          isAdmin={isAdmin}
          editing={editing}
          onEditingChange={(e) => setEditing(e)}
          modesError={modesError}
          onSubmit={submitEdit}
          onCancel={cancelConfig}
          busy={busy}
        />
      ) : null}

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

      <PreviewDialog
        open={preview !== null}
        name={preview?.name ?? ""}
        text={preview?.text ?? ""}
        onClose={() => setPreview(null)}
      />
    </section>
  );
}

/* ──────────────────────────── list view ────────────────────────────── */

function ListView({
  loading,
  compatible,
  activeTemplate,
  defaultSelected,
  selectedId,
  isAdmin,
  onSelect,
  onPreview,
  onEdit,
  onDelete,
  onUploadClick,
}: {
  loading: boolean;
  compatible: ErTemplate[];
  activeTemplate: ErTemplate | null;
  defaultSelected: boolean;
  selectedId: string;
  isAdmin: boolean;
  onSelect: (id: string) => void;
  onPreview: (t: ErTemplate) => void;
  onEdit: (t: ErTemplate) => void;
  onDelete: (id: string) => void;
  onUploadClick: () => void;
}): JSX.Element {
  return (
    <div role="radiogroup" aria-label="Template choice" className="flex flex-col">
      <div className="flex flex-col gap-[8px]">
        <DefaultCard checked={defaultSelected} onSelect={() => onSelect("default")} />
        {loading ? (
          <div className="flex items-center gap-[8px] rounded-[9px] border border-dashed border-[--color-border-subtle] bg-transparent px-[14px] py-[12px] font-mono text-[10.5px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
            <span className="inline-block h-1 w-1 animate-pulse rounded-full bg-[--color-text-tertiary]" />
            Loading templates
          </div>
        ) : (
          compatible.map((t) => (
            <TemplateCard
              key={t.id}
              template={t}
              checked={selectedId === t.id}
              canMutate={t.owner_scope === "user" || isAdmin}
              onSelect={() => onSelect(t.id)}
              onPreview={() => onPreview(t)}
              onEdit={() => onEdit(t)}
              onDelete={() => onDelete(t.id)}
            />
          ))
        )}
      </div>

      {!loading && compatible.length === 0 ? (
        <p className="px-[4px] pb-[4px] pt-[14px] text-[12.5px] italic leading-[1.5] text-[--color-text-tertiary]">
          No custom templates yet for this mode. Upload one to apply your firm's
          house style.
        </p>
      ) : null}

      <DropZone onClick={onUploadClick} />

      {activeTemplate ? (
        <div className="mt-[14px] font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
          Active: <span className="text-[--color-text-secondary]">{activeTemplate.name}</span>
        </div>
      ) : null}
    </div>
  );
}

/* ──────────────────────────── default card ─────────────────────────── */

function DefaultCard({
  checked,
  onSelect,
}: {
  checked: boolean;
  onSelect: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={checked}
      onClick={onSelect}
      className={[
        "group flex items-center gap-[12px] rounded-[9px] border px-[14px] py-[12px] text-left transition-colors",
        checked
          ? "border-[rgba(168,204,0,0.55)] bg-[rgba(212,255,0,0.06)] shadow-[0_0_0_1px_rgba(212,255,0,0.10)]"
          : "border-[--color-border-subtle] bg-[--color-bg-elevated] hover:border-[--color-border-strong] hover:bg-[--color-surface-hover]",
      ].join(" ")}
    >
      <RadioDot checked={checked} />
      <IconTile checked={checked}>
        <LayoutGrid size={15} strokeWidth={1.9} />
      </IconTile>
      <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
        <span className="flex items-center gap-[8px] text-[13.5px] font-medium text-[--color-text-primary]">
          Default
          <PillBadge tone="neutral">Built-in</PillBadge>
        </span>
        <span className="font-mono text-[10.5px] tracking-[0.02em] text-[--color-text-tertiary]">
          OpenLia framework · section toggles below
        </span>
      </span>
    </button>
  );
}

/* ──────────────────────────── template card ────────────────────────── */

function TemplateCard({
  template: t,
  checked,
  canMutate,
  onSelect,
  onPreview,
  onEdit,
  onDelete,
}: {
  template: ErTemplate;
  checked: boolean;
  canMutate: boolean;
  onSelect: () => void;
  onPreview: () => void;
  onEdit: () => void;
  onDelete: () => void;
}): JSX.Element {
  const formatLabel =
    FORMAT_LABEL[t.raw_mime] ?? t.raw_mime.split("/").pop()?.toUpperCase() ?? "FILE";
  const isGlobal = t.owner_scope === "global";
  return (
    <div
      className={[
        "group/card flex items-center gap-[12px] rounded-[9px] border px-[14px] py-[12px] transition-colors",
        checked
          ? "border-[rgba(168,204,0,0.55)] bg-[rgba(212,255,0,0.06)] shadow-[0_0_0_1px_rgba(212,255,0,0.10)]"
          : "border-[--color-border-subtle] bg-[--color-bg-elevated] hover:border-[--color-border-strong] hover:bg-[--color-surface-hover]",
      ].join(" ")}
    >
      <button
        type="button"
        role="radio"
        aria-checked={checked}
        onClick={onSelect}
        className="flex flex-1 min-w-0 items-center gap-[12px] text-left"
      >
        <RadioDot checked={checked} />
        <IconTile checked={checked}>
          <FileText size={15} strokeWidth={1.9} />
        </IconTile>
        <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
          <span className="flex min-w-0 items-center gap-[8px]">
            <span className="truncate text-[13.5px] font-medium text-[--color-text-primary]">
              {t.name}
            </span>
            <PillBadge tone={isGlobal ? "accent" : "neutral"}>
              {isGlobal ? "Global" : "Mine"}
            </PillBadge>
          </span>
          <span className="flex min-w-0 items-center gap-[8px] font-mono text-[10.5px] tracking-[0.02em] text-[--color-text-tertiary]">
            <span className="rounded-sm border border-[--color-border-subtle] bg-[--color-bg-base] px-[5px] py-[1px] text-[9px] uppercase tracking-[0.1em] text-[--color-text-secondary]">
              {formatLabel}
            </span>
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
          "flex shrink-0 items-center gap-[2px] transition-opacity",
          checked
            ? "opacity-100"
            : "opacity-0 group-hover/card:opacity-100 focus-within:opacity-100",
        ].join(" ")}
      >
        <CardIconButton title="Preview extracted text" onClick={onPreview}>
          <Eye size={13} />
        </CardIconButton>
        {canMutate ? (
          <>
            <CardIconButton title="Edit metadata" onClick={onEdit}>
              <Pencil size={13} />
            </CardIconButton>
            <CardIconButton
              title="Delete"
              onClick={onDelete}
              tone="danger"
            >
              <Trash2 size={13} />
            </CardIconButton>
          </>
        ) : null}
      </span>
    </div>
  );
}

/* ──────────────────────────── drop zone ────────────────────────────── */

function DropZone({ onClick }: { onClick: () => void }): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mt-[10px] flex items-center gap-[10px] rounded-[9px] border border-dashed border-[--color-border-strong] bg-transparent px-[14px] py-[11px] text-left text-[12.5px] text-[--color-text-secondary] transition-all hover:border-[--color-feedback-success] hover:bg-[rgba(212,255,0,0.05)] hover:text-[--color-feedback-success]"
    >
      <Upload size={14} strokeWidth={1.7} className="shrink-0 opacity-70" />
      <span className="flex-1">
        Drop a file here or click to upload your own template
      </span>
      <span className="font-mono text-[9.5px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
        DOCX · PDF · MD
      </span>
    </button>
  );
}

/* ─────────────────────── primitives ─────────────────────────────── */

function RadioDot({ checked }: { checked: boolean }): JSX.Element {
  return (
    <span
      aria-hidden="true"
      className={[
        "inline-flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full border-[1.5px] transition-colors",
        checked
          ? "border-[--color-feedback-success] bg-[--color-accent-primary]"
          : "border-[--color-border-strong]",
      ].join(" ")}
    >
      {checked ? (
        <span className="block h-[6px] w-[6px] rounded-full bg-[--color-accent-on]" />
      ) : null}
    </span>
  );
}

function IconTile({
  checked,
  children,
}: {
  checked: boolean;
  children: JSX.Element;
}): JSX.Element {
  return (
    <span
      aria-hidden="true"
      className={[
        "inline-flex h-[32px] w-[32px] flex-shrink-0 items-center justify-center rounded-[7px] border transition-colors",
        checked
          ? "border-[rgba(168,204,0,0.40)] bg-[rgba(212,255,0,0.16)] text-[--color-accent-on]"
          : "border-[--color-border-subtle] bg-[--color-bg-base] text-[--color-text-secondary]",
      ].join(" ")}
    >
      {children}
    </span>
  );
}

function PillBadge({
  tone,
  children,
}: {
  tone: "accent" | "neutral";
  children: React.ReactNode;
}): JSX.Element {
  return (
    <span
      className={[
        "inline-flex shrink-0 items-center rounded-full border px-[6px] py-[1px] font-mono text-[9px] uppercase tracking-[0.1em]",
        tone === "accent"
          ? "border-[rgba(168,204,0,0.35)] bg-[rgba(212,255,0,0.10)] text-[--color-accent-on]"
          : "border-[--color-border-subtle] bg-[--color-surface-hover] text-[--color-text-secondary]",
      ].join(" ")}
    >
      {children}
    </span>
  );
}

function CardIconButton({
  children,
  onClick,
  title,
  tone = "default",
}: {
  children: JSX.Element;
  onClick: () => void;
  title: string;
  tone?: "default" | "danger";
}): JSX.Element {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      className={[
        "inline-flex h-[26px] w-[26px] items-center justify-center rounded-[5px] border-0 bg-transparent text-[--color-text-tertiary] transition-colors",
        tone === "danger"
          ? "hover:bg-[rgba(220,80,80,0.10)] hover:text-[--color-feedback-danger]"
          : "hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]",
      ].join(" ")}
    >
      {children}
    </button>
  );
}

/* ──────────────────────────── configure view ───────────────────────── */

interface ConfigureProps {
  isAdmin: boolean;
  onCancel: () => void;
  onSubmit: () => void;
  modesError: boolean;
  busy: boolean;
}

interface UploadConfigureProps extends ConfigureProps {
  kind: "upload";
  draft: UploadDraft;
  onDraftChange: (next: UploadDraft) => void;
}

interface EditConfigureProps extends ConfigureProps {
  kind: "edit";
  editing: EditDraft;
  onEditingChange: (next: EditDraft) => void;
}

function ConfigureView(props: UploadConfigureProps | EditConfigureProps): JSX.Element {
  const isUpload = props.kind === "upload";
  const filename = isUpload ? props.draft.file.name : props.editing.filename;
  const filesize = isUpload ? props.draft.file.size : props.editing.filesize;
  const format = isUpload
    ? FORMAT_LABEL[props.draft.file.type] ??
      filename.split(".").pop()?.toUpperCase() ??
      "FILE"
    : props.editing.format;
  const name = isUpload ? props.draft.name : props.editing.name;
  const modes = isUpload ? props.draft.modes : props.editing.modes;
  const scope = isUpload ? props.draft.scope : undefined;

  const setName = (s: string) =>
    isUpload
      ? props.onDraftChange({ ...props.draft, name: s })
      : props.onEditingChange({ ...props.editing, name: s });
  const setModes = (next: Set<ReportMode>) =>
    isUpload
      ? props.onDraftChange({ ...props.draft, modes: next })
      : props.onEditingChange({ ...props.editing, modes: next });
  const setScope = (s: TemplateOwnerScope) =>
    isUpload ? props.onDraftChange({ ...props.draft, scope: s }) : undefined;

  return (
    <div className="flex flex-col">
      <button
        type="button"
        onClick={props.onCancel}
        className="mb-[10px] inline-flex h-[24px] w-fit items-center gap-[5px] rounded-[5px] pl-[4px] pr-[8px] font-display text-[12px] text-[--color-text-secondary] transition-colors hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
      >
        <ChevronLeft size={13} strokeWidth={2} />
        Back to templates
      </button>

      <div className="flex flex-col gap-[18px]">
        <div className="flex items-center gap-[12px] rounded-[9px] border border-[rgba(168,204,0,0.35)] bg-[rgba(212,255,0,0.06)] px-[14px] py-[12px]">
          <span className="inline-flex h-[32px] w-[32px] flex-shrink-0 items-center justify-center rounded-[7px] border border-[rgba(168,204,0,0.40)] bg-[rgba(212,255,0,0.16)] text-[--color-accent-on]">
            <FileText size={15} strokeWidth={1.9} />
          </span>
          <div className="flex min-w-0 flex-1 flex-col gap-[2px]">
            <div className="truncate text-[13.5px] font-medium text-[--color-text-primary]">
              {filename}
            </div>
            <div className="font-mono text-[10.5px] tracking-[0.02em] text-[--color-text-tertiary]">
              {format} · {formatBytes(filesize)}
              {isUpload ? " · ready to save" : " · on file"}
            </div>
          </div>
          <span className="inline-flex shrink-0 items-center gap-[5px] rounded-full border border-[rgba(107,130,0,0.30)] bg-[rgba(107,130,0,0.10)] px-[9px] py-[3px] font-mono text-[9px] uppercase tracking-[0.1em] text-[--color-feedback-success]">
            <Check size={9} strokeWidth={2.4} />
            {isUpload ? "Uploaded" : "Saved"}
          </span>
        </div>

        <Step
          num={1}
          title="Name this template"
          sub="Shown in the template picker. Defaults to the file name — edit if you want something cleaner."
        >
          <input
            type="text"
            aria-label="Template name"
            placeholder="e.g. House Initiation Template"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="h-[34px] w-full rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-[10px] text-[13px] text-[--color-text-primary] outline-none transition-colors focus:border-[--color-accent-primary] focus:shadow-[0_0_0_3px_rgba(212,255,0,0.18)]"
          />
        </Step>

        <Step
          num={2}
          title="Apply to report modes"
          sub="Pick the report types where this template should be available. Choose at least one."
        >
          <div className="flex flex-col gap-[6px]">
            {ALL_MODES.map((m) => {
              const checked = modes.has(m);
              return (
                <button
                  key={m}
                  type="button"
                  role="checkbox"
                  aria-checked={checked}
                  onClick={() => {
                    const next = new Set(modes);
                    if (checked) next.delete(m);
                    else next.add(m);
                    setModes(next);
                  }}
                  className={[
                    "flex items-center gap-[11px] rounded-[8px] border px-[12px] py-[10px] text-left transition-colors",
                    checked
                      ? "border-[rgba(168,204,0,0.55)] bg-[rgba(212,255,0,0.05)]"
                      : "border-[--color-border-subtle] bg-[--color-bg-base] hover:border-[--color-border-strong] hover:bg-[--color-surface-hover]",
                  ].join(" ")}
                >
                  <span
                    aria-hidden="true"
                    className={[
                      "inline-flex h-[18px] w-[18px] flex-shrink-0 items-center justify-center rounded-[5px] border-[1.5px] transition-colors",
                      checked
                        ? "border-[--color-accent-primary] bg-[--color-accent-primary] text-[--color-accent-on]"
                        : "border-[--color-border-strong] bg-[--color-bg-elevated]",
                    ].join(" ")}
                  >
                    {checked ? <Check size={11} strokeWidth={3} /> : null}
                  </span>
                  <span className="flex flex-1 flex-col gap-[1px]">
                    <span className="text-[13px] font-medium text-[--color-text-primary]">
                      {MODE_LABELS[m]}
                    </span>
                    <span className="text-[11.5px] text-[--color-text-secondary]">
                      {MODE_SUBLABELS[m]}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
          {props.modesError ? (
            <span className="mt-[2px] block text-[11.5px] text-[--color-feedback-danger]">
              Select at least one report mode.
            </span>
          ) : null}
        </Step>

        {isUpload && props.isAdmin && scope ? (
          <Step
            num={3}
            title="Where should it live?"
            sub="Mine: only you can pick it. Global: every user in this workspace can pick it."
          >
            <div
              role="radiogroup"
              aria-label="Scope"
              className="flex gap-[2px] rounded-lg border border-[--color-border-subtle] bg-[--color-bg-base] p-[3px]"
            >
              {(
                [
                  { value: "user", label: "Mine", sub: "Only you" },
                  { value: "global", label: "Global (admin)", sub: "All users" },
                ] as { value: TemplateOwnerScope; label: string; sub: string }[]
              ).map((opt) => {
                const active = opt.value === scope;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    onClick={() => setScope?.(opt.value)}
                    className={[
                      "flex-1 rounded-md px-[10px] py-[6px] text-left transition-colors",
                      active
                        ? "bg-[--color-bg-elevated] shadow-[0_1px_2px_rgba(13,13,11,0.06)]"
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
          </Step>
        ) : null}

        <div className="flex justify-end gap-[8px] pt-[2px]">
          <button
            type="button"
            onClick={props.onCancel}
            className="inline-flex h-9 items-center rounded-md border border-[--color-border-subtle] bg-transparent px-4 font-display text-[13.5px] font-medium text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={props.onSubmit}
            disabled={props.busy}
            className="inline-flex h-9 items-center rounded-md bg-[--color-accent-primary] px-4 font-display text-[13.5px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {props.busy
              ? isUpload
                ? "Uploading…"
                : "Saving…"
              : isUpload
                ? "Save Template"
                : "Save Template"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Step({
  num,
  title,
  sub,
  children,
}: {
  num: number;
  title: string;
  sub: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <div className="flex flex-col gap-[6px]">
      <div className="flex items-center gap-[10px]">
        <span className="inline-flex h-[22px] w-[22px] flex-shrink-0 items-center justify-center rounded-full bg-[--color-accent-primary] font-mono text-[11px] font-semibold text-[--color-accent-on] shadow-[0_0_0_3px_rgba(212,255,0,0.18)]">
          {num}
        </span>
        <span className="text-[14px] font-semibold tracking-[-0.005em] text-[--color-text-primary]">
          {title}
        </span>
      </div>
      <p className="mb-[6px] ml-[32px] mt-[-2px] text-[12.5px] leading-[1.5] text-[--color-text-secondary]">
        {sub}
      </p>
      {children}
    </div>
  );
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

/* ──────────────────────────── preview dialog ───────────────────────── */

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

/* ─────────────────────── public helper: template info card ─────────── */

interface TemplateInfoCardProps {
  template: ErTemplate;
}

export function TemplateInfoCard({
  template,
}: TemplateInfoCardProps): JSX.Element {
  const [preview, setPreview] = useState<{ name: string; text: string } | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const openPreview = async () => {
    try {
      const text = await fetchErTemplateExtractedText(template.id);
      setPreview({ name: template.name, text });
    } catch (e) {
      setError((e as Error).message || "preview failed");
    }
  };
  return (
    <>
      <div className="flex items-start gap-[12px] rounded-[9px] border border-[--color-border-subtle] bg-[--color-bg-base] px-[16px] py-[14px]">
        <span className="mt-[2px] inline-flex h-[22px] w-[22px] flex-shrink-0 items-center justify-center rounded-full border border-[rgba(168,204,0,0.40)] bg-[rgba(212,255,0,0.16)] text-[--color-accent-on]">
          <FileText size={12} strokeWidth={1.9} />
        </span>
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="mb-[3px] text-[13px] font-medium text-[--color-text-primary]">
            Sections defined by{" "}
            <span className="text-[--color-feedback-success]">
              {template.name}
            </span>
          </div>
          <p className="m-0 text-[12.5px] leading-[1.5] text-[--color-text-secondary]">
            Report length and section structure are inherited from the template
            file. To change the structure, edit the source file and re-upload,
            or switch back to{" "}
            <strong className="font-medium text-[--color-text-primary]">
              Default
            </strong>
            .
          </p>
          {error ? (
            <span className="mt-[6px] text-[11.5px] text-[--color-feedback-danger]">
              {error}
            </span>
          ) : null}
          <div className="mt-[10px] flex gap-[6px]">
            <button
              type="button"
              onClick={openPreview}
              className="inline-flex items-center gap-[5px] rounded-[5px] px-[8px] py-[4px] font-display text-[12px] font-medium text-[--color-feedback-success] transition-colors hover:bg-[rgba(212,255,0,0.08)]"
            >
              <Eye size={12} strokeWidth={2} />
              Preview template
            </button>
            <a
              href={erTemplateRawUrl(template.id)}
              download={template.raw_filename}
              className="inline-flex items-center gap-[5px] rounded-[5px] px-[8px] py-[4px] font-display text-[12px] font-medium text-[--color-feedback-success] transition-colors hover:bg-[rgba(212,255,0,0.08)]"
            >
              <Download size={12} strokeWidth={2} />
              Download original
            </a>
          </div>
        </div>
      </div>
      <PreviewDialog
        open={preview !== null}
        name={preview?.name ?? ""}
        text={preview?.text ?? ""}
        onClose={() => setPreview(null)}
      />
    </>
  );
}
