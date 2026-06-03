/**
 * MbCabinetView — Morning Briefing template + instructions library.
 *
 * Lists built-in and user templates / instruction profiles, supports
 * uploading new ones and deleting user-owned entries. Full-screen overlay
 * whose chrome mirrors the EU/ER overlay views (back button + mono eyebrow,
 * icon'd section headers, dashed upload pills, hover rows, dashed-card empty
 * states).
 */
import { useState } from "react";
import {
  ChevronLeft,
  FileText,
  ListChecks,
  Trash2,
  Upload,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import type { MbInstructions, MbTemplate } from "../../api/morning-briefing";
import { ConfirmDialog } from "../primitives/ConfirmDialog";

import { MbInstructionsUploadModal } from "./MbInstructionsUploadModal";
import { MbTemplateUploadModal } from "./MbTemplateUploadModal";

interface Props {
  templates: MbTemplate[];
  instructions: MbInstructions[];
  onBack: () => void;
  onUploadTemplateMarkdown: (name: string, markdown: string) => Promise<void>;
  onUploadTemplateFile: (name: string, file: File) => Promise<void>;
  onUploadInstructions: (name: string, file: File) => Promise<void>;
  onRemoveTemplate: (id: string) => Promise<void>;
  onRemoveInstructions: (id: string) => Promise<void>;
}

type PendingDelete =
  | { kind: "template"; id: string }
  | { kind: "instructions"; id: string }
  | null;

export function MbCabinetView({
  templates,
  instructions,
  onBack,
  onUploadTemplateMarkdown,
  onUploadTemplateFile,
  onUploadInstructions,
  onRemoveTemplate,
  onRemoveInstructions,
}: Props) {
  const { t } = useTranslation();
  const [templateUploadOpen, setTemplateUploadOpen] = useState(false);
  const [instructionsUploadOpen, setInstructionsUploadOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete>(null);

  const sortedTemplates = [...templates].sort((a, b) => {
    if (a.is_builtin !== b.is_builtin) return a.is_builtin ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  const sortedInstructions = [...instructions].sort((a, b) => {
    if (a.is_builtin !== b.is_builtin) return a.is_builtin ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  const removeTitle =
    pendingDelete?.kind === "instructions"
      ? t("morning_briefing.library.remove_instructions_title")
      : t("morning_briefing.library.remove_template_title");

  return (
    <div
      className="fixed inset-0 bg-[--color-bg-base] z-50 overflow-y-auto"
      data-testid="mb-cabinet"
    >
      <header className="grid grid-cols-[1fr_auto_1fr] items-center h-14 px-4 sm:px-6 border-b border-[--color-border-subtle]">
        <button
          type="button"
          onClick={onBack}
          className="justify-self-start inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-[--color-border-subtle] text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors"
        >
          <ChevronLeft size={14} /> {t("morning_briefing.library.back")}
        </button>
        <div className="flex flex-col items-center">
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
            {t("morning_briefing.library.eyebrow")}
          </span>
          <h2 className="text-[16px] font-semibold text-[--color-text-primary] m-0">
            {t("morning_briefing.library.title")}
          </h2>
        </div>
        <div />
      </header>

      <div className="max-w-[900px] mx-auto px-4 sm:px-6 py-6">
        <CabinetSection
          icon={<FileText size={14} />}
          heading={t("morning_briefing.library.templates_heading")}
          count={sortedTemplates.length}
          uploadLabel={t("morning_briefing.library.upload_template")}
          uploadTestId="mb-cabinet-upload-template"
          onUpload={() => setTemplateUploadOpen(true)}
          emptyLabel={t("morning_briefing.library.empty_templates")}
          className="mb-8"
        >
          {sortedTemplates.map((tpl) => (
            <CabinetRow
              key={tpl.id}
              icon={<FileText size={13} />}
              name={tpl.name}
              isBuiltin={tpl.is_builtin}
              builtinLabel={t("morning_briefing.library.builtin_badge")}
              deleteAria={t("morning_briefing.library.delete_aria")}
              deleteTestId={`mb-cabinet-delete-template-${tpl.id}`}
              onDelete={() =>
                setPendingDelete({ kind: "template", id: tpl.id })
              }
            />
          ))}
        </CabinetSection>

        <CabinetSection
          icon={<ListChecks size={14} />}
          heading={t("morning_briefing.library.instructions_heading")}
          count={sortedInstructions.length}
          uploadLabel={t("morning_briefing.library.upload_instructions")}
          uploadTestId="mb-cabinet-upload-instructions"
          onUpload={() => setInstructionsUploadOpen(true)}
          emptyLabel={t("morning_briefing.library.empty_instructions")}
        >
          {sortedInstructions.map((ins) => (
            <CabinetRow
              key={ins.id}
              icon={<ListChecks size={13} />}
              name={ins.name}
              isBuiltin={ins.is_builtin}
              builtinLabel={t("morning_briefing.library.builtin_badge")}
              deleteAria={t("morning_briefing.library.delete_aria")}
              deleteTestId={`mb-cabinet-delete-instructions-${ins.id}`}
              onDelete={() =>
                setPendingDelete({ kind: "instructions", id: ins.id })
              }
            />
          ))}
        </CabinetSection>
      </div>

      <MbTemplateUploadModal
        open={templateUploadOpen}
        onClose={() => setTemplateUploadOpen(false)}
        onUploadMarkdown={onUploadTemplateMarkdown}
        onUploadFile={onUploadTemplateFile}
      />
      <MbInstructionsUploadModal
        open={instructionsUploadOpen}
        onClose={() => setInstructionsUploadOpen(false)}
        onUpload={onUploadInstructions}
      />

      <ConfirmDialog
        open={pendingDelete !== null}
        title={removeTitle}
        description={t("morning_briefing.library.remove_description")}
        confirmLabel={t("morning_briefing.library.remove_confirm")}
        destructive
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          const target = pendingDelete;
          setPendingDelete(null);
          if (!target) return;
          if (target.kind === "template") void onRemoveTemplate(target.id);
          else void onRemoveInstructions(target.id);
        }}
      />
    </div>
  );
}

function CabinetSection({
  icon,
  heading,
  count,
  uploadLabel,
  uploadTestId,
  onUpload,
  emptyLabel,
  className = "",
  children,
}: {
  icon: React.ReactNode;
  heading: string;
  count: number;
  uploadLabel: string;
  uploadTestId: string;
  onUpload: () => void;
  emptyLabel: string;
  className?: string;
  children: React.ReactNode;
}) {
  const isEmpty = count === 0;
  return (
    <section className={className}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="inline-flex items-center gap-2 text-[15px] font-semibold text-[--color-text-primary]">
          <span aria-hidden="true" className="text-[--color-text-secondary]">
            {icon}
          </span>
          {heading}
          {count > 0 ? (
            <span className="font-mono text-[11px] tabular-nums text-[--color-text-tertiary]">
              {count}
            </span>
          ) : null}
        </h3>
        <button
          type="button"
          onClick={onUpload}
          data-testid={uploadTestId}
          className="inline-flex items-center gap-[6px] rounded-md border border-dashed border-[--color-border-strong] bg-transparent px-[10px] py-[5px] font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-solid hover:border-[--color-feedback-success] hover:text-[--color-feedback-success] transition-colors"
        >
          <Upload size={11} strokeWidth={2} /> {uploadLabel}
        </button>
      </div>
      {isEmpty ? (
        <p className="text-[13px] text-[--color-text-tertiary] border border-dashed border-[--color-border-subtle] rounded-[12px] bg-[--color-bg-elevated] px-4 py-8 text-center">
          {emptyLabel}
        </p>
      ) : (
        <ul className="border border-[--color-border-subtle] rounded-lg overflow-hidden divide-y divide-[--color-border-subtle]">
          {children}
        </ul>
      )}
    </section>
  );
}

function CabinetRow({
  icon,
  name,
  isBuiltin,
  builtinLabel,
  deleteAria,
  deleteTestId,
  onDelete,
}: {
  icon: React.ReactNode;
  name: string;
  isBuiltin: boolean;
  builtinLabel: string;
  deleteAria: string;
  deleteTestId: string;
  onDelete: () => void;
}) {
  return (
    <li className="flex items-center gap-3 px-4 py-3 bg-[--color-bg-elevated] hover:bg-[--color-surface-hover] transition-colors">
      <span aria-hidden="true" className="text-[--color-text-tertiary]">
        {icon}
      </span>
      <span className="flex-1 text-[14px] text-[--color-text-primary] truncate">
        {name}
      </span>
      {isBuiltin ? (
        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary] border border-[--color-border-subtle] rounded px-1.5 py-px">
          {builtinLabel}
        </span>
      ) : (
        <button
          type="button"
          onClick={onDelete}
          aria-label={deleteAria}
          data-testid={deleteTestId}
          className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-tertiary] hover:text-[--color-feedback-error] hover:bg-[--color-surface-hover] transition-colors"
        >
          <Trash2 size={14} />
        </button>
      )}
    </li>
  );
}
