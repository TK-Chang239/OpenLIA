/**
 * MbCabinetView — Morning Briefing template + instructions library.
 *
 * Lists built-in and user templates / instruction profiles, supports
 * uploading new ones and deleting user-owned entries. Full-screen overlay
 * mirroring EUCabinetView's chrome.
 */
import { useState } from "react";
import { Trash2 } from "lucide-react";
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
      <header className="flex items-center justify-between h-14 px-4 sm:px-6 border-b border-[--color-border-subtle]">
        <button
          type="button"
          onClick={onBack}
          className="text-sm text-[--color-accent-primary]"
        >
          {t("morning_briefing.library.back")}
        </button>
        <h2 className="text-xl font-semibold">
          {t("morning_briefing.library.title")}
        </h2>
        <span className="w-32" />
      </header>

      <div className="max-w-[900px] mx-auto px-4 sm:px-6 py-6">
        {/* Templates */}
        <section className="mb-8">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-semibold text-[--color-text-primary]">
              {t("morning_briefing.library.templates_heading")}
            </h3>
            <button
              type="button"
              onClick={() => setTemplateUploadOpen(true)}
              data-testid="mb-cabinet-upload-template"
              className="inline-flex items-center h-8 px-3 rounded-md border border-[--color-border-subtle] text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover]"
            >
              {t("morning_briefing.library.upload_template")}
            </button>
          </div>
          {sortedTemplates.length === 0 ? (
            <p className="text-[13px] text-[--color-text-tertiary] border border-dashed border-[--color-border-subtle] rounded-lg px-4 py-6 text-center">
              {t("morning_briefing.library.empty_templates")}
            </p>
          ) : (
            <ul className="border border-[--color-border-subtle] rounded-lg overflow-hidden divide-y divide-[--color-border-subtle]">
              {sortedTemplates.map((tpl) => (
                <li
                  key={tpl.id}
                  className="flex items-center gap-3 px-4 py-3 bg-[--color-bg-elevated]"
                >
                  <span className="flex-1 text-[14px] text-[--color-text-primary]">
                    {tpl.name}
                  </span>
                  {tpl.is_builtin ? (
                    <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
                      {t("morning_briefing.library.builtin_badge")}
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() =>
                        setPendingDelete({ kind: "template", id: tpl.id })
                      }
                      aria-label={t("morning_briefing.library.delete_aria")}
                      className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-tertiary] hover:text-[--color-feedback-error] hover:bg-[--color-surface-hover]"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Instructions */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-semibold text-[--color-text-primary]">
              {t("morning_briefing.library.instructions_heading")}
            </h3>
            <button
              type="button"
              onClick={() => setInstructionsUploadOpen(true)}
              data-testid="mb-cabinet-upload-instructions"
              className="inline-flex items-center h-8 px-3 rounded-md border border-[--color-border-subtle] text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover]"
            >
              {t("morning_briefing.library.upload_instructions")}
            </button>
          </div>
          {sortedInstructions.length === 0 ? (
            <p className="text-[13px] text-[--color-text-tertiary] border border-dashed border-[--color-border-subtle] rounded-lg px-4 py-6 text-center">
              {t("morning_briefing.library.empty_instructions")}
            </p>
          ) : (
            <ul className="border border-[--color-border-subtle] rounded-lg overflow-hidden divide-y divide-[--color-border-subtle]">
              {sortedInstructions.map((ins) => (
                <li
                  key={ins.id}
                  className="flex items-center gap-3 px-4 py-3 bg-[--color-bg-elevated]"
                >
                  <span className="flex-1 text-[14px] text-[--color-text-primary]">
                    {ins.name}
                  </span>
                  {ins.is_builtin ? (
                    <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
                      {t("morning_briefing.library.builtin_badge")}
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() =>
                        setPendingDelete({ kind: "instructions", id: ins.id })
                      }
                      aria-label={t("morning_briefing.library.delete_aria")}
                      className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-tertiary] hover:text-[--color-feedback-error] hover:bg-[--color-surface-hover]"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
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
