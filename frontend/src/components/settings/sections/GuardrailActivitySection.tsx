import { type FC, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  listGuardrailEvents,
  wipeGuardrailEvents,
  type GuardrailEvent,
} from "../../../api/guardrailEvents";

interface Props {
  mode: "personal" | "company";
}

const CATEGORIES = [
  "",
  "leaked_prompt",
  "broken_character",
  "advice_phrasing",
  "fabricated_quote",
  "disclaimer_regression",
  "price_prediction",
  "padding",
  "no_advice",
  "out_of_scope",
  "no_prompt_leak",
  "no_price_targets",
];

export const GuardrailActivitySection: FC<Props> = ({ mode }) => {
  const { t } = useTranslation();
  const [days, setDays] = useState(7);
  const [category, setCategory] = useState("");
  const [rows, setRows] = useState<GuardrailEvent[]>([]);

  const refresh = useCallback(async () => {
    const items = await listGuardrailEvents({
      since_days: days,
      category: category || undefined,
    });
    setRows(items);
  }, [days, category]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <section>
      <h2 className="text-base font-semibold">{t('settings.guardrails.title')}</h2>
      <div className="mt-2 flex items-center gap-2">
        <label className="text-xs">
          {t('settings.guardrails.filter_last')}
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="ml-1"
          >
            <option value={1}>{t('settings.guardrails.range_1d')}</option>
            <option value={7}>{t('settings.guardrails.range_7d')}</option>
            <option value={30}>{t('settings.guardrails.range_30d')}</option>
          </select>
        </label>
        <label className="text-xs">
          {t('settings.guardrails.filter_category')}
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="ml-1"
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c || t('settings.guardrails.filter_all')}
              </option>
            ))}
          </select>
        </label>
        {mode === "personal" && (
          <button
            onClick={async () => {
              await wipeGuardrailEvents();
              await refresh();
            }}
            className="ml-auto text-xs text-red-600 underline"
          >
            {t('settings.guardrails.wipe_all')}
          </button>
        )}
      </div>
      <table className="mt-3 w-full text-xs">
        <thead className="text-slate-500">
          <tr>
            <th className="text-left">{t('settings.guardrails.col_when')}</th>
            <th className="text-left">{t('settings.guardrails.col_desk')}</th>
            <th className="text-left">{t('settings.guardrails.col_type')}</th>
            <th className="text-left">{t('settings.guardrails.col_category')}</th>
            <th className="text-left">{t('settings.guardrails.col_action')}</th>
            <th className="text-left">{t('settings.guardrails.col_excerpt')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-slate-100">
              <td>{new Date(r.created_at).toLocaleString()}</td>
              <td>{r.department_id}</td>
              <td>{r.event_type}</td>
              <td>{r.category}</td>
              <td>{r.action_taken}</td>
              <td className="truncate max-w-xs" title={r.response_excerpt}>
                {r.response_excerpt}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
};
