import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  createReportTemplate,
  deleteReportTemplate,
  ingestTemplateDocument,
  listReportTemplates,
  parseTemplateMarkdown,
  type ParsedTemplate,
  type ReportTemplate,
} from "../../../api/report-templates";
import { TemplateReview } from "../../templates/TemplateReview";

type DraftStage = "idle" | "ingesting" | "parsing" | "ready" | "saving";

interface Draft {
  name: string;
  markdown: string;
  parsed: ParsedTemplate | null;
  stage: DraftStage;
  error: string | null;
}

const EMPTY_DRAFT: Draft = {
  name: "",
  markdown: "",
  parsed: null,
  stage: "idle",
  error: null,
};

export function CustomTemplatesSection(): JSX.Element {
  const { t } = useTranslation();
  const [items, setItems] = useState<ReportTemplate[] | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [listError, setListError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setItems(await listReportTemplates());
      setListError(null);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "failed to list");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleFile = async (file: File) => {
    const name = draft.name || file.name.replace(/\.[^.]+$/, "");
    setDraft({ ...EMPTY_DRAFT, name, stage: "ingesting" });
    try {
      const ingested = await ingestTemplateDocument(file);
      setDraft((d) => ({ ...d, markdown: ingested.markdown, stage: "parsing" }));
      const parsed = await parseTemplateMarkdown(ingested.markdown, name);
      setDraft((d) => ({ ...d, parsed, stage: "ready" }));
    } catch (err) {
      setDraft((d) => ({
        ...d,
        stage: "idle",
        error: err instanceof Error ? err.message : "upload failed",
      }));
    }
  };

  const handleMarkdownChange = async (markdown: string) => {
    setDraft((d) => ({ ...d, markdown, stage: "parsing" }));
    try {
      const parsed = await parseTemplateMarkdown(
        markdown,
        draft.name || "Untitled template",
      );
      setDraft((d) => ({ ...d, parsed, stage: "ready", error: null }));
    } catch (err) {
      setDraft((d) => ({
        ...d,
        stage: "ready",
        error: err instanceof Error ? err.message : "parse failed",
      }));
    }
  };

  const handleSave = async () => {
    if (!draft.parsed) return;
    setDraft((d) => ({ ...d, stage: "saving", error: null }));
    try {
      await createReportTemplate({
        name: draft.name || "Untitled template",
        templateSpec: draft.parsed.template_spec,
        sourceMarkdown: draft.markdown,
      });
      setDraft(EMPTY_DRAFT);
      await refresh();
    } catch (err) {
      setDraft((d) => ({
        ...d,
        stage: "ready",
        error: err instanceof Error ? err.message : "save failed",
      }));
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteReportTemplate(id);
      await refresh();
    } catch (err) {
      setListError(err instanceof Error ? err.message : "delete failed");
    }
  };

  const busy =
    draft.stage === "ingesting" ||
    draft.stage === "parsing" ||
    draft.stage === "saving";

  return (
    <div className="space-y-6 p-6">
      <header>
        <h2 className="text-xl font-semibold text-text-primary">
          {t("settings.custom_templates.title")}
        </h2>
        <p className="mt-1 text-sm text-text-secondary">
          {t("settings.custom_templates.subtitle")}
        </p>
      </header>

      <section
        className="rounded border border-border-subtle bg-bg-base p-4"
        aria-label={t("settings.custom_templates.upload.title")}
      >
        <h3 className="mb-3 text-sm font-semibold text-text-primary">
          {t("settings.custom_templates.upload.title")}
        </h3>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex-1 text-sm text-text-secondary">
            <span className="mb-1 block">
              {t("settings.custom_templates.upload.name_label")}
            </span>
            <input
              type="text"
              className="w-full rounded border border-border-subtle bg-bg-base px-2 py-1 text-sm"
              value={draft.name}
              onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
              placeholder={t("settings.custom_templates.upload.name_placeholder")}
            />
          </label>
          <label className="text-sm text-text-secondary">
            <span className="mb-1 block">
              {t("settings.custom_templates.upload.file_label")}
            </span>
            <input
              type="file"
              accept=".md,.markdown,.txt,.docx"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void handleFile(file);
                // Reset input so re-uploading the same file fires onChange.
                e.target.value = "";
              }}
              data-testid="template-upload-input"
            />
          </label>
        </div>
        {draft.error ? (
          <p className="mt-3 text-sm text-status-danger" role="alert">
            {draft.error}
          </p>
        ) : null}
      </section>

      {draft.parsed ? (
        <section className="space-y-3 rounded border border-border-subtle bg-bg-base p-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">
              {t("settings.custom_templates.review.heading")}
            </h3>
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded border border-border-subtle px-3 py-1 text-sm text-text-secondary hover:bg-surface-hover"
                onClick={() => setDraft(EMPTY_DRAFT)}
                disabled={busy}
              >
                {t("settings.custom_templates.review.discard")}
              </button>
              <button
                type="button"
                className="rounded bg-accent-primary px-3 py-1 text-sm text-white disabled:opacity-50"
                onClick={() => void handleSave()}
                disabled={busy || draft.parsed.sections.length === 0}
                data-testid="template-save-button"
              >
                {draft.stage === "saving"
                  ? t("common.saving")
                  : t("settings.custom_templates.review.save")}
              </button>
            </div>
          </div>
          <TemplateReview parsed={draft.parsed} />
          <details className="rounded border border-border-subtle bg-bg-subtle p-3">
            <summary className="cursor-pointer text-xs font-semibold text-text-secondary">
              {t("settings.custom_templates.review.edit_markdown")}
            </summary>
            <textarea
              className="mt-2 h-48 w-full rounded border border-border-subtle bg-bg-base p-2 font-mono text-xs"
              value={draft.markdown}
              onChange={(e) => void handleMarkdownChange(e.target.value)}
              spellCheck={false}
              data-testid="template-markdown-editor"
            />
          </details>
        </section>
      ) : null}

      <section
        className="rounded border border-border-subtle bg-bg-base p-4"
        aria-label={t("settings.custom_templates.list.title")}
      >
        <h3 className="mb-3 text-sm font-semibold text-text-primary">
          {t("settings.custom_templates.list.title")}
        </h3>
        {listError ? (
          <p className="text-sm text-status-danger" role="alert">
            {listError}
          </p>
        ) : items === null ? (
          <p className="text-sm text-text-secondary">{t("common.loading")}</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-text-secondary">
            {t("settings.custom_templates.list.empty")}
          </p>
        ) : (
          <ul className="divide-y divide-border-subtle">
            {items.map((tmpl) => {
              const spec = tmpl.template_spec as {
                body_sections?: unknown[];
                synthesis_sections?: unknown[];
              };
              const sectionCount =
                (spec.body_sections?.length ?? 0) +
                (spec.synthesis_sections?.length ?? 0);
              return (
                <li
                  key={tmpl.id}
                  className="flex items-center justify-between py-3"
                  data-testid={`template-row-${tmpl.id}`}
                >
                  <div>
                    <p className="text-sm font-medium text-text-primary">
                      {tmpl.name}
                    </p>
                    <p className="text-xs text-text-secondary">
                      {t("settings.custom_templates.list.section_count", {
                        count: sectionCount,
                      })}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleDelete(tmpl.id)}
                    className="rounded border border-border-subtle px-2 py-1 text-xs text-status-danger hover:bg-surface-hover"
                  >
                    {t("common.delete")}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
