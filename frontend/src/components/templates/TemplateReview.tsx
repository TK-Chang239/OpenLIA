import { useTranslation } from "react-i18next";
import type { ParsedTemplate } from "../../api/report-templates";

interface Props {
  parsed: ParsedTemplate;
}

export function TemplateReview({ parsed }: Props): JSX.Element {
  const { t } = useTranslation();
  const sectionCount = parsed.sections.length;
  const documentFmKeys = Object.keys(parsed.document_frontmatter ?? {});

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="rounded border border-border-subtle bg-bg-base p-4">
        <h4 className="mb-2 text-sm font-semibold text-text-secondary">
          {t("settings.custom_templates.review.preview_heading")}
        </h4>
        {parsed.global_preface ? (
          <section className="mb-4">
            <h5 className="text-xs uppercase tracking-wide text-text-secondary">
              {t("settings.custom_templates.review.preface_label")}
            </h5>
            <pre className="mt-1 whitespace-pre-wrap text-xs text-text-primary">
              {parsed.global_preface}
            </pre>
          </section>
        ) : null}
        {documentFmKeys.length > 0 ? (
          <section>
            <h5 className="text-xs uppercase tracking-wide text-text-secondary">
              {t("settings.custom_templates.review.doc_frontmatter_label")}
            </h5>
            <ul className="mt-1 text-xs text-text-primary">
              {documentFmKeys.map((key) => (
                <li key={key}>
                  <span className="font-mono text-text-secondary">{key}</span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>

      <div className="rounded border border-border-subtle bg-bg-base p-4">
        <h4 className="mb-2 text-sm font-semibold text-text-secondary">
          {t("settings.custom_templates.review.sections_heading", {
            count: sectionCount,
          })}
        </h4>
        {sectionCount === 0 ? (
          <p className="text-sm text-text-secondary">
            {t("settings.custom_templates.review.no_sections")}
          </p>
        ) : (
          <ol className="space-y-3">
            {parsed.sections.map((s, idx) => {
              const fmKeys = Object.keys(s.frontmatter ?? {});
              return (
                <li
                  key={s.id}
                  className="rounded border border-border-subtle bg-bg-subtle p-3"
                  data-testid={`parsed-section-${s.id}`}
                >
                  <div className="flex items-baseline justify-between">
                    <h5 className="text-sm font-semibold text-text-primary">
                      {idx + 1}. {s.title}
                    </h5>
                    <code className="text-xs text-text-secondary">{s.id}</code>
                  </div>
                  {fmKeys.length > 0 ? (
                    <ul className="mt-2 flex flex-wrap gap-1 text-xs">
                      {fmKeys.map((k) => (
                        <li
                          key={k}
                          className="rounded bg-accent-primary/10 px-2 py-0.5 font-mono text-accent-primary"
                        >
                          {k}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  <p
                    className="mt-2 line-clamp-3 text-xs text-text-secondary"
                    title={s.brief}
                  >
                    {s.brief.slice(0, 280) || (
                      <em>
                        {t("settings.custom_templates.review.empty_brief")}
                      </em>
                    )}
                  </p>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </div>
  );
}
