import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  listReportTemplates,
  type ReportTemplate,
} from "../../api/report-templates";

interface Props {
  /** Selected template id, or null for the built-in default framework. */
  selectedId: string | null;
  onChange: (id: string | null) => void;
}

const DEFAULT_VALUE = "__default__";

export function FrameworkTemplatePicker({
  selectedId,
  onChange,
}: Props): JSX.Element {
  const { t } = useTranslation();
  const [templates, setTemplates] = useState<ReportTemplate[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    listReportTemplates()
      .then((items) => {
        if (!cancelled) setTemplates(items);
      })
      .catch(() => {
        if (!cancelled) setTemplates([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Auto-clear a stale selection if the user deleted the template elsewhere.
  useEffect(() => {
    if (
      templates !== null &&
      selectedId !== null &&
      !templates.some((tpl) => tpl.id === selectedId)
    ) {
      onChange(null);
    }
  }, [templates, selectedId, onChange]);

  const value = selectedId ?? DEFAULT_VALUE;

  return (
    <label className="flex items-center gap-2 text-xs text-text-secondary">
      <span>{t("equity_research.framework_template.label")}</span>
      <select
        className="rounded border border-border-subtle bg-bg-base px-2 py-1 text-xs text-text-primary"
        value={value}
        onChange={(e) =>
          onChange(e.target.value === DEFAULT_VALUE ? null : e.target.value)
        }
        data-testid="framework-template-picker"
      >
        <option value={DEFAULT_VALUE}>
          {t("equity_research.framework_template.default_option")}
        </option>
        {templates?.map((tpl) => (
          <option key={tpl.id} value={tpl.id}>
            {tpl.name}
          </option>
        ))}
      </select>
    </label>
  );
}
