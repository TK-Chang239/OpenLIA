export interface CacheStats {
  total_entries: number;
  total_bytes: number;
}

export async function fetchCacheStats(): Promise<CacheStats> {
  const r = await fetch("/api/cache/stats");
  if (!r.ok) throw new Error(`failed: ${r.status}`);
  return r.json();
}

export async function clearCache(ticker?: string): Promise<{ deleted: number }> {
  const qs = ticker ? `?ticker=${encodeURIComponent(ticker)}` : "";
  const r = await fetch(`/api/cache/documents${qs}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`failed: ${r.status}`);
  return r.json();
}
