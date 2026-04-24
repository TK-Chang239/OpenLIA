import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createHolding,
  deleteHolding,
  exportCsvUrl,
  fetchAnalytics,
  fetchHoldings,
  importCsv,
  refreshPrices,
  type AnalyticsResponse,
  type PortfolioHolding,
} from "../api/portfolio";

interface AddFormState {
  ticker: string;
  shares: string;
  cost_basis: string;
  currency: string;
}

const EMPTY_FORM: AddFormState = {
  ticker: "",
  shares: "",
  cost_basis: "",
  currency: "USD",
};

function formatMoney(v: string | null): string {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return v;
  return n.toLocaleString(undefined, {
    style: "decimal",
    maximumFractionDigits: 2,
  });
}

function formatPct(v: string | null): string {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return v;
  return `${(n * 100).toFixed(2)}%`;
}

export default function PortfolioPage() {
  const [holdings, setHoldings] = useState<PortfolioHolding[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<AddFormState>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [refreshMsg, setRefreshMsg] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [rows, summary] = await Promise.all([fetchHoldings(), fetchAnalytics()]);
      setHoldings(rows);
      setAnalytics(summary);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const onAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.ticker.trim() || submitting) return;
    setSubmitting(true);
    try {
      await createHolding({
        ticker: form.ticker,
        shares: form.shares || null,
        cost_basis: form.cost_basis || null,
        currency: form.currency || "USD",
      });
      setForm(EMPTY_FORM);
      await reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const onDelete = async (id: string) => {
    try {
      await deleteHolding(id);
      await reload();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const onRefresh = async () => {
    setRefreshMsg(null);
    try {
      await refreshPrices();
      await reload();
      setRefreshMsg("Prices refreshed");
    } catch (e) {
      setRefreshMsg((e as Error).message);
    }
  };

  const onImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    try {
      const res = await importCsv(text);
      if (res.errors.length) {
        setError(`Imported ${res.created.length}; ${res.errors.length} errors`);
      }
      await reload();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      e.target.value = "";
    }
  };

  const analyticsByHolding = useMemo(() => {
    const map = new Map<string, AnalyticsResponse["positions"][number]>();
    analytics?.positions.forEach((p) => map.set(p.holding_id, p));
    return map;
  }, [analytics]);

  return (
    <div className="p-6 space-y-6" data-testid="portfolio-page">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-[--color-text-primary]">Portfolio</h1>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onRefresh}
            className="px-3 py-1.5 rounded-[--radius-sm] border border-[--color-border-subtle] text-sm"
          >
            Refresh prices
          </button>
          <a
            href={exportCsvUrl()}
            className="px-3 py-1.5 rounded-[--radius-sm] border border-[--color-border-subtle] text-sm"
          >
            Export CSV
          </a>
          <label className="px-3 py-1.5 rounded-[--radius-sm] border border-[--color-border-subtle] text-sm cursor-pointer">
            Import CSV
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={onImport}
              className="hidden"
            />
          </label>
        </div>
      </header>

      {error && (
        <div className="p-3 rounded-[--radius-sm] bg-[--color-danger-surface] text-sm">
          {error}
        </div>
      )}
      {refreshMsg && (
        <div className="text-sm text-[--color-text-tertiary]">{refreshMsg}</div>
      )}

      {analytics && (
        <section className="grid grid-cols-3 gap-4">
          <div className="p-4 rounded-[--radius-md] border border-[--color-border-subtle]">
            <div className="text-xs text-[--color-text-tertiary]">Market Value</div>
            <div className="text-xl font-semibold">
              {formatMoney(analytics.total_market_value)}
            </div>
          </div>
          <div className="p-4 rounded-[--radius-md] border border-[--color-border-subtle]">
            <div className="text-xs text-[--color-text-tertiary]">Cost Basis</div>
            <div className="text-xl font-semibold">
              {formatMoney(analytics.total_cost_basis)}
            </div>
          </div>
          <div className="p-4 rounded-[--radius-md] border border-[--color-border-subtle]">
            <div className="text-xs text-[--color-text-tertiary]">Unrealized P/L</div>
            <div className="text-xl font-semibold">
              {formatMoney(analytics.total_unrealized_pl)} (
              {formatPct(analytics.total_unrealized_pl_pct)})
            </div>
          </div>
        </section>
      )}

      <form onSubmit={onAdd} className="flex flex-wrap gap-2 items-end">
        <div>
          <label className="block text-xs text-[--color-text-tertiary]">Ticker</label>
          <input
            value={form.ticker}
            onChange={(e) => setForm({ ...form, ticker: e.target.value })}
            className="px-2 py-1 border border-[--color-border-subtle] rounded-[--radius-sm] text-sm"
            placeholder="AAPL"
          />
        </div>
        <div>
          <label className="block text-xs text-[--color-text-tertiary]">Shares</label>
          <input
            value={form.shares}
            onChange={(e) => setForm({ ...form, shares: e.target.value })}
            className="px-2 py-1 border border-[--color-border-subtle] rounded-[--radius-sm] text-sm w-24"
          />
        </div>
        <div>
          <label className="block text-xs text-[--color-text-tertiary]">Cost Basis</label>
          <input
            value={form.cost_basis}
            onChange={(e) => setForm({ ...form, cost_basis: e.target.value })}
            className="px-2 py-1 border border-[--color-border-subtle] rounded-[--radius-sm] text-sm w-28"
          />
        </div>
        <div>
          <label className="block text-xs text-[--color-text-tertiary]">Currency</label>
          <input
            value={form.currency}
            onChange={(e) => setForm({ ...form, currency: e.target.value })}
            className="px-2 py-1 border border-[--color-border-subtle] rounded-[--radius-sm] text-sm w-20"
          />
        </div>
        <button
          type="submit"
          disabled={submitting || !form.ticker.trim()}
          className="px-3 py-1.5 rounded-[--radius-sm] bg-[--color-accent] text-[--color-text-on-accent] text-sm"
        >
          Add holding
        </button>
      </form>

      <section>
        {loading ? (
          <div className="text-sm text-[--color-text-tertiary]">Loading…</div>
        ) : holdings.length === 0 ? (
          <div className="text-sm text-[--color-text-tertiary]">
            Your portfolio is empty. Add a holding above or import a CSV.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[--color-text-tertiary] border-b border-[--color-border-subtle]">
                <th className="py-2">Ticker</th>
                <th>Shares</th>
                <th>Cost Basis</th>
                <th>Last Price</th>
                <th>Market Value</th>
                <th>P/L</th>
                <th>Weight</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h) => {
                const a = analyticsByHolding.get(h.id);
                return (
                  <tr key={h.id} className="border-b border-[--color-border-subtle]">
                    <td className="py-2 font-medium">{h.ticker}</td>
                    <td>{formatMoney(h.shares)}</td>
                    <td>{formatMoney(h.cost_basis)}</td>
                    <td>{formatMoney(a?.last_price ?? null)}</td>
                    <td>{formatMoney(a?.market_value ?? null)}</td>
                    <td>
                      {formatMoney(a?.unrealized_pl ?? null)} (
                      {formatPct(a?.unrealized_pl_pct ?? null)})
                    </td>
                    <td>{formatPct(a?.weight ?? null)}</td>
                    <td>
                      <button
                        type="button"
                        onClick={() => onDelete(h.id)}
                        className="text-xs text-[--color-text-tertiary] hover:text-[--color-danger]"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
