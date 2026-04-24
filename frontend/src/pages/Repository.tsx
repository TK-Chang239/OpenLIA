import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchRepoFacets,
  listRepoItemsFiltered,
  saveToRepo,
  unsaveFromRepo,
  type RepoFacets,
  type RepoRow,
  type RepoSort,
} from "../api/repo";
import { reportPdfUrl } from "../api/reports";

const SORT_LABELS: Record<RepoSort, string> = {
  saved_desc: "Date saved (newest)",
  saved_asc: "Date saved (oldest)",
  generated_desc: "Date generated (newest)",
  generated_asc: "Date generated (oldest)",
  department_asc: "Department (A→Z)",
  filename_asc: "Filename (A→Z)",
};

const PAGE_SIZE = 50;

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

interface PendingRemoval {
  row: RepoRow;
  timeoutId: number;
}

export default function Repository(): JSX.Element {
  const [q, setQ] = useState("");
  const [selectedDepartments, setSelectedDepartments] = useState<string[]>([]);
  const [sort, setSort] = useState<RepoSort>("saved_desc");
  const [rows, setRows] = useState<RepoRow[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [facets, setFacets] = useState<RepoFacets>({ departments: [], total: 0 });
  const [pendingRemove, setPendingRemove] = useState<RepoRow | null>(null);
  const [pendingUndo, setPendingUndo] = useState<PendingRemoval | null>(null);

  const loadPage = useCallback(
    async (pageNum: number, reset: boolean) => {
      setLoading(true);
      setError(null);
      try {
        const body = await listRepoItemsFiltered({
          q: q || undefined,
          departments: selectedDepartments.length > 0 ? selectedDepartments : undefined,
          sort,
          page: pageNum,
          page_size: PAGE_SIZE,
        });
        setHasMore(body.has_more);
        setRows((prev) => (reset ? body.items : [...prev, ...body.items]));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load saved reports");
      } finally {
        setLoading(false);
      }
    },
    [q, selectedDepartments, sort],
  );

  // Reload when filters / sort change
  useEffect(() => {
    setPage(1);
    void loadPage(1, true);
  }, [loadPage]);

  useEffect(() => {
    void fetchRepoFacets().then(setFacets).catch(() => {});
  }, []);

  const toggleDepartment = (slug: string) => {
    setSelectedDepartments((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug],
    );
  };

  const clearFilters = () => {
    setQ("");
    setSelectedDepartments([]);
  };

  const confirmRemove = async () => {
    if (!pendingRemove) return;
    const row = pendingRemove;
    setPendingRemove(null);
    setRows((prev) => prev.filter((r) => r.id !== row.id));
    try {
      await unsaveFromRepo(row.report_id);
      const timeoutId = window.setTimeout(() => {
        setPendingUndo(null);
      }, 4000);
      setPendingUndo({ row, timeoutId });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove");
      // restore row on error
      setRows((prev) => [row, ...prev]);
    }
  };

  const undoRemove = async () => {
    if (!pendingUndo) return;
    window.clearTimeout(pendingUndo.timeoutId);
    const { row } = pendingUndo;
    setPendingUndo(null);
    try {
      await saveToRepo(row.report_id);
      setRows((prev) => [row, ...prev]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to undo");
    }
  };

  const loadMore = () => {
    if (loading || !hasMore) return;
    const next = page + 1;
    setPage(next);
    void loadPage(next, false);
  };

  const hasActiveFilters = useMemo(
    () => q !== "" || selectedDepartments.length > 0,
    [q, selectedDepartments],
  );

  return (
    <div className="repo-page" style={{ padding: "24px", maxWidth: "960px", margin: "0 auto" }}>
      <header style={{ marginBottom: "16px" }}>
        <h1 style={{ margin: 0 }}>Repository</h1>
        <p style={{ color: "var(--color-text-secondary)", margin: "4px 0 0" }}>
          {facets.total} saved report{facets.total === 1 ? "" : "s"}
        </p>
      </header>

      <section
        aria-label="filters"
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "8px",
          alignItems: "center",
          marginBottom: "16px",
        }}
      >
        <input
          type="search"
          aria-label="Search filename"
          placeholder="Search filename..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ flex: "1 1 240px", padding: "8px 12px" }}
        />
        <select
          aria-label="Sort"
          value={sort}
          onChange={(e) => setSort(e.target.value as RepoSort)}
          style={{ padding: "8px 12px" }}
        >
          {(Object.keys(SORT_LABELS) as RepoSort[]).map((k) => (
            <option key={k} value={k}>
              {SORT_LABELS[k]}
            </option>
          ))}
        </select>
        {hasActiveFilters && (
          <button type="button" onClick={clearFilters}>
            Clear filters
          </button>
        )}
      </section>

      {facets.departments.length > 0 && (
        <section
          aria-label="departments"
          style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "16px" }}
        >
          {facets.departments.map((d) => {
            const active = selectedDepartments.includes(d.slug);
            return (
              <button
                key={d.slug}
                type="button"
                aria-pressed={active}
                onClick={() => toggleDepartment(d.slug)}
                style={{
                  padding: "4px 10px",
                  borderRadius: "999px",
                  border: "1px solid",
                  borderColor: active
                    ? "var(--color-accent-primary)"
                    : "var(--color-border-subtle)",
                  background: active ? "var(--color-accent-primary)" : "transparent",
                  color: active ? "var(--color-accent-on)" : "inherit",
                  cursor: "pointer",
                }}
              >
                {d.slug} ({d.count})
              </button>
            );
          })}
        </section>
      )}

      {error && (
        <div role="alert" style={{ color: "var(--color-feedback-error)", marginBottom: "12px" }}>
          {error}
        </div>
      )}

      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {rows.map((row) => (
          <li
            key={row.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              padding: "12px",
              borderBottom: "1px solid var(--color-border-subtle)",
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis" }}>
                {row.filename}
              </div>
              <div style={{ fontSize: "0.85rem", color: "var(--color-text-secondary)" }}>
                {row.department} · generated {formatDate(row.generated_at)} · saved{" "}
                {formatDate(row.saved_at)}
              </div>
            </div>
            <a
              href={reportPdfUrl(row.report_id)}
              target="_blank"
              rel="noreferrer"
              aria-label={`Download ${row.filename}`}
            >
              Download
            </a>
            <button
              type="button"
              aria-label={`Remove ${row.filename}`}
              onClick={() => setPendingRemove(row)}
            >
              Remove
            </button>
          </li>
        ))}
      </ul>

      {rows.length === 0 && !loading && (
        <div style={{ padding: "48px 0", textAlign: "center", color: "var(--color-text-secondary)" }}>
          {hasActiveFilters ? "No reports match your filters." : "No saved reports yet."}
        </div>
      )}

      {loading && <div style={{ padding: "12px", textAlign: "center" }}>Loading...</div>}

      {hasMore && !loading && (
        <div style={{ padding: "12px", textAlign: "center" }}>
          <button type="button" onClick={loadMore}>
            Load more
          </button>
        </div>
      )}

      {!hasMore && rows.length > 0 && !loading && (
        <div style={{ padding: "12px", textAlign: "center", color: "var(--color-text-tertiary)" }}>
          All reports loaded
        </div>
      )}

      {pendingRemove && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Confirm removal"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.4)",
            display: "grid",
            placeItems: "center",
            zIndex: 1000,
          }}
        >
          <div style={{ background: "var(--color-bg-elevated)", padding: "20px", borderRadius: "8px", maxWidth: "400px", border: "1px solid var(--color-border-subtle)" }}>
            <h2 style={{ marginTop: 0 }}>Remove from Repository?</h2>
            <p>This will remove "{pendingRemove.filename}" from your Repository.</p>
            <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
              <button type="button" onClick={() => setPendingRemove(null)}>
                Cancel
              </button>
              <button type="button" onClick={confirmRemove}>
                Remove
              </button>
            </div>
          </div>
        </div>
      )}

      {pendingUndo && (
        <div
          role="status"
          style={{
            position: "fixed",
            bottom: "24px",
            left: "50%",
            transform: "translateX(-50%)",
            background: "var(--neutral-900)",
            color: "var(--neutral-50)",
            padding: "10px 16px",
            borderRadius: "6px",
            display: "flex",
            gap: "12px",
            alignItems: "center",
            zIndex: 1001,
          }}
        >
          <span>Removed "{pendingUndo.row.filename}"</span>
          <button
            type="button"
            onClick={undoRemove}
            style={{ background: "transparent", color: "var(--color-accent-primary)", border: "none", cursor: "pointer" }}
          >
            Undo
          </button>
        </div>
      )}
    </div>
  );
}
