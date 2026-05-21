import { useEffect, useState } from "react";
import { fetchCacheStats, clearCache } from "../../../api/cache";
import type { CacheStats } from "../../../api/cache";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const mb = bytes / (1024 * 1024);
  if (mb >= 0.1) return `${mb.toFixed(2)} MB`;
  const kb = bytes / 1024;
  if (kb >= 0.1) return `${kb.toFixed(1)} KB`;
  return `${bytes} B`;
}

export function CacheAdmin() {
  const [stats, setStats] = useState<CacheStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [ticker, setTicker] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadStats() {
    setLoading(true);
    setError(null);
    try {
      const s = await fetchCacheStats();
      setStats(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadStats();
  }, []);

  async function handleClearTicker() {
    if (!ticker.trim()) return;
    setMessage(null);
    setError(null);
    try {
      const result = await clearCache(ticker.trim());
      setMessage(`Deleted ${result.deleted} document(s) for ticker ${ticker.trim()}.`);
      setTicker("");
      await loadStats();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleClearAll() {
    if (!window.confirm("Clear all cached documents? This cannot be undone.")) return;
    setMessage(null);
    setError(null);
    try {
      const result = await clearCache();
      setMessage(`Deleted ${result.deleted} document(s).`);
      await loadStats();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <section className="cache-admin flex flex-col gap-4">
      <h2 className="text-lg font-semibold text-[--color-text-primary]">Cache Admin</h2>

      {loading && (
        <p className="text-sm text-[--color-text-tertiary]">Loading...</p>
      )}

      {!loading && stats && (
        <div className="flex flex-col gap-1 text-sm text-[--color-text-secondary]">
          <p>
            <span className="font-medium text-[--color-text-primary]">
              {stats.total_entries}
            </span>
            {" "}cached document{stats.total_entries !== 1 ? "s" : ""}
          </p>
          <p>
            <span className="font-medium text-[--color-text-primary]">
              {formatBytes(stats.total_bytes)}
            </span>
            {" "}stored
          </p>
        </div>
      )}

      {error && (
        <p className="text-sm text-[--color-feedback-error]">{error}</p>
      )}

      {message && (
        <p className="text-sm text-[--color-feedback-success]">{message}</p>
      )}

      <div className="flex flex-col gap-2">
        <label className="text-xs font-medium uppercase tracking-wider text-[--color-text-tertiary]">
          Clear by ticker
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="e.g. NVDA"
            className="flex-1 rounded border border-[--color-border-subtle] bg-[--color-surface-secondary] px-3 py-1.5 text-sm text-[--color-text-primary] placeholder:text-[--color-text-muted] focus:outline-none focus:ring-1 focus:ring-[--color-accent]"
          />
          <button
            onClick={handleClearTicker}
            disabled={!ticker.trim()}
            className="rounded px-3 py-1.5 text-sm font-medium bg-[--color-surface-secondary] text-[--color-text-secondary] border border-[--color-border-subtle] hover:bg-[--color-surface-hover] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Clear for ticker
          </button>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-xs font-medium uppercase tracking-wider text-[--color-text-tertiary]">
          Flush all
        </label>
        <button
          onClick={handleClearAll}
          className="self-start rounded px-3 py-1.5 text-sm font-medium bg-[--color-surface-secondary] text-[--color-feedback-error] border border-[--color-border-subtle] hover:bg-[--color-surface-hover]"
        >
          Clear all cache
        </button>
      </div>

      <button
        onClick={loadStats}
        className="self-start text-xs text-[--color-text-tertiary] hover:text-[--color-text-secondary] underline underline-offset-2"
      >
        Refresh stats
      </button>
    </section>
  );
}
