import { useEffect, useMemo, useRef, useState } from "react";
import type { JSX, ReactNode } from "react";
import { motion } from "framer-motion";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  fetchRepoFacets,
  saveToRepo,
  saveV3RunToRepo,
  unsaveFromRepo,
  unsaveV3RunFromRepo,
  type RepoFacets,
  type RepoRow,
} from "../api/repo";
import { deleteReport } from "../api/reports";
import { deleteV3Run } from "../api/equity-research-v3";
import { DeleteReportDialog } from "../components/report/DeleteReportDialog";
import { useRepoList } from "../hooks/useRepoList";
import { useFileViewer } from "../components/viewer/FileViewerContext";
import { useSavedReportsOptional } from "../components/repo/SavedReportsContext";
import { useToast } from "../components/primitives/Toast";
import { departmentLabel } from "../lib/department-colors";
import { RepoFilterBar } from "../components/repo/RepoFilterBar";
import { RepoFilterChips } from "../components/repo/RepoFilterChips";
import { SortDropdown } from "../components/repo/SortDropdown";
import { RepoListItem } from "../components/repo/RepoListItem";
import { RepoListSkeleton } from "../components/repo/RepoListSkeleton";
import { RepoEmptyState } from "../components/repo/RepoEmptyState";
import { RemoveConfirmDialog } from "../components/repo/RemoveConfirmDialog";

const STAGGER = 0.06;
const RETENTION_DAYS = 7;
const MS_PER_DAY = 86_400_000;

function ageDays(iso: string, now: number = Date.now()): number {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return 0;
  return (now - t) / MS_PER_DAY;
}

function isPastRetention(row: RepoRow): boolean {
  return ageDays(row.generated_at) >= RETENTION_DAYS;
}

function Reveal({
  delay,
  children,
}: {
  delay: number;
  children: ReactNode;
}): JSX.Element {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: "easeOut", delay: delay * STAGGER }}
    >
      {children}
    </motion.div>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

export default function Repository(): JSX.Element {
  const { t } = useTranslation();
  const list = useRepoList();
  const { open: openViewer } = useFileViewer();
  const savedReports = useSavedReportsOptional();
  const toast = useToast();
  const [facets, setFacets] = useState<RepoFacets>({ departments: [], total: 0 });
  const [pendingRemove, setPendingRemove] = useState<RepoRow | null>(null);
  const [pendingDelete, setPendingDelete] = useState<RepoRow | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const openParam = searchParams.get("open");
  const openParamHandledRef = useRef<string | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    void fetchRepoFacets().then(setFacets).catch(() => {});
  }, []);

  // Cmd/Ctrl+K focuses the search input. Honors the kbd hint we surface in
  // the search field; no global command palette behind it.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        searchInputRef.current?.focus();
        searchInputRef.current?.select();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const activeFilterCount = useMemo(() => {
    let n = 0;
    if (list.params.q !== "") n += 1;
    n += list.params.departments.length;
    if (list.params.generated_from !== "" || list.params.generated_to !== "") n += 1;
    if (list.params.saved_from !== "" || list.params.saved_to !== "") n += 1;
    return n;
  }, [list.params]);

  const filtersActive = activeFilterCount > 0;

  const handleOpen = (row: RepoRow) => {
    const metadata = `${departmentLabel(row.department)} · Generated ${formatDate(row.generated_at)} · Saved ${formatDate(row.saved_at)}`;
    // The Repo page hides the FileViewer's save-to-repo button (we're
    // already in the repo — the action would always be "remove" and
    // the toolbar's three-dot menu carries that). Branch the source
    // shape on engine so v3 rows render through the v3 detail
    // renderer instead of the v1 ``ReportRenderer`` path.
    if (row.engine === "v3") {
      openViewer({
        filename: row.filename,
        kind: "report",
        metadata,
        source: { kind: "v3_report", reportId: row.report_id },
        initialSaved: true,
        hideSaveToRepoButton: true,
      });
      return;
    }
    openViewer({
      filename: row.filename,
      kind: "report",
      metadata,
      source: { kind: "report", reportId: row.report_id },
      initialSaved: true,
      hideSaveToRepoButton: true,
    });
  };

  // Deep-link: /repository?open=<report_id> opens the matching row in the
  // FileViewer once the list has loaded. If the row isn't found after the
  // first load completes, surface a toast. Param strips on resolution.
  useEffect(() => {
    if (!openParam) return;
    if (openParamHandledRef.current === openParam) return;
    if (list.loading) return;
    const row = list.rows.find((r) => r.report_id === openParam);
    openParamHandledRef.current = openParam;
    if (row) {
      handleOpen(row);
    } else {
      toast.push({
        title: t("repository.report_not_in_repo"),
        tone: "info",
        durationMs: 4000,
      });
    }
    const next = new URLSearchParams(searchParams);
    next.delete("open");
    setSearchParams(next, { replace: true });
  }, [openParam, list.loading, list.rows, toast, searchParams, setSearchParams, t]);

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    const row = pendingDelete;
    setPendingDelete(null);
    const removedIndex = list.rows.findIndex((r) => r.id === row.id);
    list.removeRow(row.id);
    try {
      if (row.engine === "v3") {
        await deleteV3Run(row.report_id);
        savedReports?.markV3Unsaved(row.report_id);
      } else {
        await deleteReport(row.report_id);
        savedReports?.markUnsaved(row.report_id);
      }
      toast.push({
        title: t("repository.report_deleted"),
        durationMs: 3000,
      });
    } catch {
      list.restoreRow(row, removedIndex);
      toast.push({
        title: t("repository.delete_failed"),
        tone: "error",
        durationMs: 4000,
      });
    }
  };

  const confirmRemove = async () => {
    if (!pendingRemove) return;
    const row = pendingRemove;
    setPendingRemove(null);
    const removedIndex = list.rows.findIndex((r) => r.id === row.id);
    list.removeRow(row.id);
    try {
      if (row.engine === "v3") {
        await unsaveV3RunFromRepo(row.report_id);
        savedReports?.markV3Unsaved(row.report_id);
      } else {
        await unsaveFromRepo(row.report_id);
        savedReports?.markUnsaved(row.report_id);
      }
      toast.push({
        title: t("repository.removed_from_repo"),
        durationMs: 4000,
        undo: {
          label: t("repository.undo"),
          onClick: async () => {
            try {
              if (row.engine === "v3") {
                await saveV3RunToRepo(row.report_id);
                savedReports?.markV3Saved(row.report_id);
              } else {
                await saveToRepo(row.report_id);
                savedReports?.markSaved(row.report_id);
              }
              list.restoreRow(row, removedIndex);
              toast.push({ title: t("repository.report_restored"), tone: "success", durationMs: 2000 });
            } catch {
              toast.push({
                title: t("repository.restore_failed"),
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
        title: t("repository.remove_failed"),
        tone: "error",
        durationMs: 4000,
      });
    }
  };

  const showSkeleton = list.loading && list.rows.length === 0;
  const showEmpty = !list.loading && list.rows.length === 0;
  const emptyMode: "no-saved" | "no-match" = filtersActive ? "no-match" : "no-saved";
  const totalLabel = facets.total === 1 ? t("repository.saved_report_one") : t("repository.saved_report_other");

  return (
    <div className="flex h-full flex-col bg-[--color-bg-base]">
      <Reveal delay={0}>
        <header className="flex h-[56px] flex-shrink-0 items-center border-b border-[--color-border-subtle] bg-[--color-bg-base] px-6">
          <h1 className="whitespace-nowrap text-[20px] font-semibold tracking-[-0.01em] text-[--color-text-primary]">
            {t("repository.title")}
            <span className="ml-3 font-mono text-[10px] font-normal tracking-[0.1em] text-[--color-text-tertiary]">
              {facets.total} {totalLabel}
            </span>
          </h1>
        </header>
      </Reveal>

      <Reveal delay={1}>
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
          activeFilterCount={activeFilterCount}
          searchInputRef={searchInputRef}
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
      </Reveal>

      <Reveal delay={2}>
        <RepoFilterChips
          q={list.params.q}
          departments={list.params.departments}
          generatedFrom={list.params.generated_from}
          generatedTo={list.params.generated_to}
          savedFrom={list.params.saved_from}
          savedTo={list.params.saved_to}
          onRemoveSearch={() => list.setParams({ q: "" })}
          onRemoveDepartment={(slug) =>
            list.setParams({
              departments: list.params.departments.filter((d) => d !== slug),
            })
          }
          onRemoveGeneratedRange={() =>
            list.setParams({ generated_from: "", generated_to: "" })
          }
          onRemoveSavedRange={() => list.setParams({ saved_from: "", saved_to: "" })}
          onClearAll={list.clearFilters}
        />
      </Reveal>

      <Reveal delay={3}>
        <div className="flex items-center gap-3 px-6 pb-[6px] pt-[10px]">
          <SortDropdown value={list.params.sort} onChange={(s) => list.setParams({ sort: s })} />
          <span className="ml-auto whitespace-nowrap font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
            {t("repository.showing", { shown: list.rows.length, total: facets.total })}
            {activeFilterCount > 0
              ? ` · ${
                  activeFilterCount === 1
                    ? t("repository.filter_applied_one", { count: activeFilterCount })
                    : t("repository.filter_applied_other", { count: activeFilterCount })
                }`
              : ""}
          </span>
        </div>
      </Reveal>

      {list.error ? (
        <div role="alert" className="px-6 py-3 text-sm text-[--color-feedback-error]">
          {list.error}
        </div>
      ) : null}

      <div className="flex-1 overflow-y-auto px-6 pb-7 pt-1">
        {showSkeleton ? (
          <div className="overflow-hidden rounded-[--radius-xl] border border-[--color-border-subtle] bg-[--color-bg-base]">
            <RepoListSkeleton />
          </div>
        ) : showEmpty ? (
          <RepoEmptyState
            mode={emptyMode}
            onClearFilters={emptyMode === "no-match" ? list.clearFilters : undefined}
          />
        ) : (
          <ul
            className="divide-y divide-[--color-border-subtle] overflow-hidden rounded-[--radius-xl] border border-[--color-border-subtle] bg-[--color-bg-base]"
            data-testid="repo-list"
          >
            {list.rows.map((row) => (
              <RepoListItem
                key={row.id}
                row={row}
                onOpen={handleOpen}
                onRemove={(r) => {
                  if (isPastRetention(r)) {
                    setPendingDelete(r);
                  } else {
                    setPendingRemove(r);
                  }
                }}
              />
            ))}
          </ul>
        )}
        <div ref={list.sentinelRef} data-testid="repo-sentinel" />
        {list.rows.length > 0 && list.loading ? (
          <div
            className="py-[18px] pt-[18px] text-center font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]"
            role="status"
          >
            {t("repository.loading_more", { shown: list.rows.length, total: facets.total })}
          </div>
        ) : null}
        {list.rows.length > 0 && !list.hasMore && !list.loading ? (
          <div className="py-[18px] pt-[18px] text-center font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
            {t("repository.end_of_results", { shown: list.rows.length })}
          </div>
        ) : null}
      </div>

      <RemoveConfirmDialog
        open={pendingRemove !== null}
        filename={pendingRemove?.filename ?? ""}
        onCancel={() => setPendingRemove(null)}
        onConfirm={() => void confirmRemove()}
      />

      <DeleteReportDialog
        open={pendingDelete !== null}
        reportTitle={pendingDelete?.filename ?? ""}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => void confirmDelete()}
      />
    </div>
  );
}
