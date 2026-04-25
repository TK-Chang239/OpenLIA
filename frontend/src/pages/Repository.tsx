import { useEffect, useMemo, useState } from "react";
import { fetchRepoFacets, saveToRepo, unsaveFromRepo, type RepoFacets, type RepoRow } from "../api/repo";
import { reportPdfUrl } from "../api/reports";
import { useRepoList } from "../hooks/useRepoList";
import { useFileViewer, kindFromFilename } from "../components/viewer/FileViewerContext";
import { useToast } from "../components/primitives/Toast";
import { departmentLabel } from "../lib/department-colors";
import { RepoFilterBar } from "../components/repo/RepoFilterBar";
import { RepoFilterChips } from "../components/repo/RepoFilterChips";
import { SortDropdown } from "../components/repo/SortDropdown";
import { RepoListItem } from "../components/repo/RepoListItem";
import { RepoListSkeleton } from "../components/repo/RepoListSkeleton";
import { RepoEmptyState } from "../components/repo/RepoEmptyState";
import { RemoveConfirmDialog } from "../components/repo/RemoveConfirmDialog";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

export default function Repository(): JSX.Element {
  const list = useRepoList();
  const { open: openViewer } = useFileViewer();
  const toast = useToast();
  const [facets, setFacets] = useState<RepoFacets>({ departments: [], total: 0 });
  const [pendingRemove, setPendingRemove] = useState<RepoRow | null>(null);

  useEffect(() => {
    void fetchRepoFacets().then(setFacets).catch(() => {});
  }, []);

  const filtersActive = useMemo(
    () =>
      list.params.q !== "" ||
      list.params.departments.length > 0 ||
      list.params.generated_from !== "" ||
      list.params.generated_to !== "" ||
      list.params.saved_from !== "" ||
      list.params.saved_to !== "",
    [list.params],
  );

  const handleOpen = (row: RepoRow) => {
    openViewer({
      filename: row.filename,
      kind: kindFromFilename(row.filename),
      metadata: `${departmentLabel(row.department)} · Generated ${formatDate(row.generated_at)} · Saved ${formatDate(row.saved_at)}`,
      source: { kind: "report", reportId: row.report_id },
      initialSaved: true,
      hideSaveToRepoButton: true,
    });
  };

  const confirmRemove = async () => {
    if (!pendingRemove) return;
    const row = pendingRemove;
    setPendingRemove(null);
    const removedIndex = list.rows.findIndex((r) => r.id === row.id);
    list.removeRow(row.id);
    try {
      await unsaveFromRepo(row.report_id);
      toast.push({
        title: "Removed from Repository",
        durationMs: 4000,
        undo: {
          label: "Undo",
          onClick: async () => {
            try {
              await saveToRepo(row.report_id);
              list.restoreRow(row, removedIndex);
              toast.push({ title: "Report restored.", tone: "success", durationMs: 2000 });
            } catch {
              toast.push({
                title: "Failed to restore. Try again.",
                tone: "error",
                durationMs: 4000,
              });
            }
          },
        },
      });
    } catch {
      list.restoreRow(row, removedIndex);
      toast.push({
        title: "Failed to remove. Try again.",
        tone: "error",
        durationMs: 4000,
      });
    }
  };

  const showSkeleton = list.loading && list.rows.length === 0;
  const showEmpty = !list.loading && list.rows.length === 0;
  const emptyMode: "no-saved" | "no-match" = filtersActive ? "no-match" : "no-saved";

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center h-14 flex-shrink-0 px-6 border-b border-[--color-border-subtle] bg-[--color-bg-base]">
        <h1 className="text-xl font-semibold text-[--color-text-primary]">Repository</h1>
        <span className="ml-auto text-sm text-[--color-text-tertiary]">
          {facets.total} saved {facets.total === 1 ? "report" : "reports"}
        </span>
      </header>

      <RepoFilterBar
        q={list.params.q}
        onQChange={(v) => list.setParams({ q: v })}
        facets={facets}
        selectedDepartments={list.params.departments}
        generatedFrom={list.params.generated_from}
        generatedTo={list.params.generated_to}
        savedFrom={list.params.saved_from}
        savedTo={list.params.saved_to}
        filtersActive={filtersActive}
        onApplyFilters={(next) =>
          list.setParams({
            departments: next.departments,
            generated_from: next.generated_from,
            generated_to: next.generated_to,
            saved_from: next.saved_from,
            saved_to: next.saved_to,
          })
        }
      />

      <RepoFilterChips
        q={list.params.q}
        departments={list.params.departments}
        generatedFrom={list.params.generated_from}
        generatedTo={list.params.generated_to}
        savedFrom={list.params.saved_from}
        savedTo={list.params.saved_to}
        onRemoveSearch={() => list.setParams({ q: "" })}
        onRemoveDepartment={(slug) =>
          list.setParams({ departments: list.params.departments.filter((d) => d !== slug) })
        }
        onRemoveGeneratedRange={() =>
          list.setParams({ generated_from: "", generated_to: "" })
        }
        onRemoveSavedRange={() => list.setParams({ saved_from: "", saved_to: "" })}
        onClearAll={list.clearFilters}
      />

      <div className="flex items-center px-6 py-2">
        <SortDropdown value={list.params.sort} onChange={(s) => list.setParams({ sort: s })} />
      </div>

      {list.error ? (
        <div role="alert" className="px-6 py-3 text-sm text-[--color-feedback-error]">
          {list.error}
        </div>
      ) : null}

      <div className="flex-1 overflow-y-auto">
        {showSkeleton ? (
          <div className="border border-[--color-border-subtle] rounded-[--radius-lg] overflow-hidden mx-6 my-2">
            <RepoListSkeleton />
          </div>
        ) : showEmpty ? (
          <RepoEmptyState
            mode={emptyMode}
            onClearFilters={emptyMode === "no-match" ? list.clearFilters : undefined}
          />
        ) : (
          <ul
            className="divide-y divide-[--color-border-subtle] border border-[--color-border-subtle] rounded-[--radius-lg] overflow-hidden mx-6 my-2"
            data-testid="repo-list"
          >
            {list.rows.map((row) => (
              <RepoListItem
                key={row.id}
                row={row}
                downloadUrl={reportPdfUrl(row.report_id)}
                onOpen={handleOpen}
                onRemove={(r) => setPendingRemove(r)}
              />
            ))}
          </ul>
        )}
        <div ref={list.sentinelRef} data-testid="repo-sentinel" />
        {list.rows.length > 0 && list.loading ? (
          <div className="text-center py-4 text-xs text-[--color-text-tertiary]" role="status">
            Loading...
          </div>
        ) : null}
        {list.rows.length > 0 && !list.hasMore && !list.loading ? (
          <div className="text-xs text-[--color-text-tertiary] text-center py-4">
            All reports loaded
          </div>
        ) : null}
      </div>

      <RemoveConfirmDialog
        open={pendingRemove !== null}
        filename={pendingRemove?.filename ?? ""}
        onCancel={() => setPendingRemove(null)}
        onConfirm={() => void confirmRemove()}
      />
    </div>
  );
}
