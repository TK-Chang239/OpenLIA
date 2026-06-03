import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarClock, FileText, Library, Search } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  deleteMbRun,
  type MbRunSummary,
  type MbSchedule,
} from "../../api/morning-briefing";
import { MbBigCard } from "../../components/morning-briefing/feed/MbBigCard";
import { MbEmptyPage } from "../../components/morning-briefing/feed/MbEmptyPage";
import { MbGeneratingCard } from "../../components/morning-briefing/feed/MbGeneratingCard";
import { MbHero } from "../../components/morning-briefing/feed/MbHero";
import {
  MbFeedSection,
  MbSectionEmpty,
} from "../../components/morning-briefing/feed/MbFeedSection";
import { MbReportRow } from "../../components/morning-briefing/feed/MbReportRow";
import {
  groupReports,
  searchReports,
} from "../../components/morning-briefing/feed/mbFeedHelpers";
import { pickEarliestNextBriefing } from "../../lib/morning-briefing/next-briefing";
import { MbCabinetView } from "../../components/morning-briefing/MbCabinetView";
import { MbRunNowModal } from "../../components/morning-briefing/MbRunNowModal";
import { MbSchedulesView } from "../../components/morning-briefing/MbSchedulesView";
import { ScheduleEditorModal } from "../../components/morning-briefing/ScheduleEditorModal";
import { ConfirmDialog } from "../../components/primitives/ConfirmDialog";
import { useFileViewer } from "../../components/viewer/FileViewerContext";
import { useMbInstructions } from "../../hooks/useMbInstructions";
import { useMbRunStream } from "../../hooks/useMbRunStream";
import { useMbRuns } from "../../hooks/useMbRuns";
import { useMbSchedules } from "../../hooks/useMbSchedules";
import { useMbTemplates } from "../../hooks/useMbTemplates";

function findRun(
  runs: MbRunSummary[],
  reportId: string,
): MbRunSummary | undefined {
  return runs.find((r) => r.report_id === reportId);
}

function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      data-testid="mb-skeleton"
      className={`bg-[--color-surface-hover] rounded-[--radius-md] animate-pulse ${className}`}
    />
  );
}

export default function MorningBriefing() {
  const { t } = useTranslation();
  const {
    runs,
    refresh: refreshRuns,
    loading: runsLoading,
    error: runsError,
  } = useMbRuns();
  const {
    schedules,
    create: createSchedule,
    update: updateSchedule,
    remove: removeSchedule,
  } = useMbSchedules();
  const {
    templates,
    create: createTemplate,
    upload: uploadTemplate,
    remove: removeTemplate,
  } = useMbTemplates();
  const {
    instructions,
    upload: uploadInstructions,
    remove: removeInstructions,
  } = useMbInstructions();

  const [schedulesOpen, setSchedulesOpen] = useState(false);
  const [cabinetOpen, setCabinetOpen] = useState(false);
  const [runNowOpen, setRunNowOpen] = useState(false);
  const [editorSchedule, setEditorSchedule] = useState<MbSchedule | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [liveReportId, setLiveReportId] = useState<string | null>(null);
  const [pendingRemoval, setPendingRemoval] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const fv = useFileViewer();
  const stream = useMbRunStream(liveReportId);

  const removeReport = useCallback(
    async (reportId: string) => {
      await deleteMbRun(reportId);
      await refreshRuns();
    },
    [refreshRuns],
  );

  const openReport = useCallback(
    (reportId: string) => {
      const match = findRun(runs, reportId);
      fv.open({
        filename: match?.subject ?? t("morning_briefing.viewer_metadata"),
        kind: "report",
        metadata: t("morning_briefing.viewer_metadata"),
        source: { kind: "mb_report", reportId },
        onDelete: () => removeReport(reportId),
      });
    },
    [fv, runs, removeReport, t],
  );

  useEffect(() => {
    if (stream.status === "completed") {
      void refreshRuns();
    } else if (stream.status === "cancelled" || stream.status === "failed") {
      setLiveReportId(null);
      void refreshRuns();
    }
  }, [stream.status, refreshRuns]);

  const filtered = useMemo(() => searchReports(runs, search), [runs, search]);
  const groups = useMemo(() => groupReports(filtered), [filtered]);
  const searching = search.trim().length > 0;

  const todayReports = useMemo(
    () =>
      liveReportId
        ? groups.today.filter((r) => r.report_id !== liveReportId)
        : groups.today,
    [groups.today, liveReportId],
  );

  const heroToday =
    !liveReportId && todayReports.length > 0 ? todayReports[0] : null;
  const restToday = heroToday ? todayReports.slice(1) : todayReports;

  const liveCount = useMemo(() => {
    const running = runs.filter(
      (r) => r.status === "running" && r.report_id !== liveReportId,
    ).length;
    return running + (liveReportId ? 1 : 0);
  }, [runs, liveReportId]);

  const heroStats = useMemo(() => {
    const all = groupReports(runs);
    return {
      briefingsThisWeek: all.today.length + all.thisWeek.length,
      activeSchedules: schedules.filter((s) => s.is_enabled).length,
      nextRun: pickEarliestNextBriefing(schedules)?.display ?? null,
    };
  }, [runs, schedules]);

  const hasError = Boolean(runsError);
  const initialLoading = runsLoading && runs.length === 0;
  const allEmpty =
    !initialLoading && !hasError && runs.length === 0 && !liveReportId;

  function formatHeroStamp(iso: string): string {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const date = d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
    const time = d
      .toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
      .replace(/^0/, "");
    return `${date} · ${time} ET`;
  }

  const liveTitle =
    stream.status === "completed"
      ? t("morning_briefing.report_ready")
      : t("morning_briefing.generating_report");

  const openEditor = useCallback((schedule: MbSchedule | null) => {
    setEditorSchedule(schedule);
    setEditorOpen(true);
  }, []);

  async function handleSaveSchedule(
    payload: Parameters<typeof createSchedule>[0],
  ): Promise<void> {
    if (editorSchedule) {
      await updateSchedule(editorSchedule.id, payload);
    } else {
      await createSchedule(payload);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <header className="h-[52px] flex items-center gap-3 px-6 flex-shrink-0 border-b border-[--color-border-subtle]">
        <h1 className="text-[20px] font-semibold tracking-[-0.01em] text-[--color-text-primary]">
          {t("morning_briefing.title")}
        </h1>
        <div className="flex-1" />
        {liveCount > 0 ? (
          <span
            data-testid="mb-live-pill"
            className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-full bg-[--color-accent-subtle] font-mono text-[10px] tracking-[0.08em] uppercase text-[--color-feedback-success]"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] animate-live-pulse" />
            {t("morning_briefing.live_pill", { count: liveCount })}
          </span>
        ) : null}
        <button
          type="button"
          onClick={() => setSchedulesOpen(true)}
          className="inline-flex items-center gap-1.5 h-8 px-3 border border-[--color-border-subtle] rounded-md bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors duration-[--duration-normal] text-[12.5px]"
        >
          <CalendarClock size={13} /> {t("morning_briefing.schedules_button")}
          <span className="font-mono text-[10px] text-[--color-text-tertiary]">
            {schedules.length}
          </span>
        </button>
        <button
          type="button"
          onClick={() => setCabinetOpen(true)}
          className="inline-flex items-center gap-1.5 h-8 px-3 border border-[--color-border-subtle] rounded-md bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors duration-[--duration-normal] text-[12.5px]"
        >
          <Library size={13} /> {t("morning_briefing.library_button")}
        </button>
        <button
          type="button"
          onClick={() => setRunNowOpen(true)}
          className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] hover:bg-[--color-accent-hover] transition-colors duration-[--duration-normal] text-[12.5px] font-medium"
        >
          <FileText size={13} /> {t("morning_briefing.run_now")}
        </button>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[1200px] mx-auto px-8 pt-7 pb-16">
          {hasError ? (
            <div
              role="alert"
              className="mb-4 flex items-center justify-between gap-4 border border-[--color-feedback-error] rounded-[--radius-md] px-4 py-2 text-sm text-[--color-feedback-error]"
            >
              <span>{t("morning_briefing.load_failed")}</span>
              <button
                type="button"
                onClick={() => void refreshRuns()}
                className="text-sm font-medium underline"
              >
                {t("morning_briefing.retry")}
              </button>
            </div>
          ) : null}

          {initialLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-[140px]" />
              <Skeleton className="h-12" />
              <Skeleton className="h-20" />
              <Skeleton className="h-20" />
            </div>
          ) : allEmpty ? (
            <MbEmptyPage
              onRunNow={() => setRunNowOpen(true)}
              onOpenLibrary={() => setCabinetOpen(true)}
            />
          ) : (
            <>
              <div
                className="animate-feed-fade-up"
                style={{ animationDelay: "80ms" }}
              >
                <MbHero
                  briefingsThisWeek={heroStats.briefingsThisWeek}
                  activeSchedules={heroStats.activeSchedules}
                  nextRun={heroStats.nextRun}
                />
              </div>

              <div
                className="animate-feed-fade-up flex items-center gap-2 flex-wrap mb-[22px]"
                style={{ animationDelay: "120ms" }}
              >
                <div className="inline-flex items-center gap-2 h-8 px-3 border border-[--color-border-subtle] rounded-md bg-[--color-bg-elevated] flex-1 max-w-[320px]">
                  <Search size={13} className="text-[--color-text-tertiary]" />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder={t("morning_briefing.feed.search_placeholder")}
                    aria-label={t("morning_briefing.feed.search_aria")}
                    className="border-0 bg-transparent outline-none text-[13px] text-[--color-text-primary] w-full placeholder:text-[--color-text-tertiary]"
                  />
                </div>
              </div>

              <div
                className="animate-feed-fade-up"
                style={{ animationDelay: "160ms" }}
              >
                <MbFeedSection
                  label={t("morning_briefing.today")}
                  count={todayReports.length + (liveReportId ? 1 : 0)}
                >
                  {liveReportId ? (
                    <div className="mb-2">
                      {stream.status === "completed" ? (
                        <MbBigCard
                          title={liveTitle}
                          status="complete"
                          reportId={liveReportId}
                          highlights={
                            findRun(runs, liveReportId)?.highlights ?? null
                          }
                          onOpen={openReport}
                          onRemove={(id) => setPendingRemoval(id)}
                        />
                      ) : (
                        <MbGeneratingCard stream={stream} />
                      )}
                    </div>
                  ) : null}
                  {heroToday ? (
                    <div className="mb-2">
                      <MbBigCard
                        title={heroToday.subject}
                        stamp={formatHeroStamp(heroToday.created_at)}
                        status="complete"
                        reportId={heroToday.report_id}
                        highlights={heroToday.highlights ?? null}
                        onOpen={openReport}
                        onRemove={(id) => setPendingRemoval(id)}
                      />
                    </div>
                  ) : null}
                  {todayReports.length === 0 && !liveReportId ? (
                    <MbSectionEmpty
                      message={
                        searching
                          ? t("morning_briefing.no_matching_briefings_today")
                          : t("morning_briefing.no_briefings_today")
                      }
                    />
                  ) : null}
                  {restToday.length > 0 ? (
                    <div className="flex flex-col gap-2">
                      {restToday.map((r) => (
                        <MbReportRow
                          key={r.report_id}
                          report={r}
                          onOpen={openReport}
                          onRemove={(id) => setPendingRemoval(id)}
                        />
                      ))}
                    </div>
                  ) : null}
                </MbFeedSection>
              </div>

              <div
                className="animate-feed-fade-up"
                style={{ animationDelay: "240ms" }}
              >
                <MbFeedSection
                  label={t("morning_briefing.this_week")}
                  count={groups.thisWeek.length}
                >
                  {groups.thisWeek.length === 0 ? (
                    <MbSectionEmpty
                      message={
                        searching
                          ? t("morning_briefing.no_matching_briefings")
                          : t("morning_briefing.no_briefings_this_week")
                      }
                    />
                  ) : (
                    <div className="flex flex-col gap-2">
                      {groups.thisWeek.map((r) => (
                        <MbReportRow
                          key={r.report_id}
                          report={r}
                          onOpen={openReport}
                          onRemove={(id) => setPendingRemoval(id)}
                        />
                      ))}
                    </div>
                  )}
                </MbFeedSection>
              </div>

              {groups.older.length > 0 ? (
                <div
                  className="animate-feed-fade-up"
                  style={{ animationDelay: "320ms" }}
                >
                  <MbFeedSection
                    label={t("morning_briefing.older")}
                    count={groups.older.length}
                  >
                    <div className="flex flex-col gap-2">
                      {groups.older.map((r) => (
                        <MbReportRow
                          key={r.report_id}
                          report={r}
                          onOpen={openReport}
                          onRemove={(id) => setPendingRemoval(id)}
                        />
                      ))}
                    </div>
                  </MbFeedSection>
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>

      {schedulesOpen ? (
        <MbSchedulesView
          schedules={schedules}
          onBack={() => setSchedulesOpen(false)}
          onAdd={() => openEditor(null)}
          onEdit={(s) => openEditor(s)}
          onRemove={async (id) => {
            await removeSchedule(id);
          }}
        />
      ) : null}

      {cabinetOpen ? (
        <MbCabinetView
          templates={templates}
          instructions={instructions}
          onBack={() => setCabinetOpen(false)}
          onUploadTemplateMarkdown={async (name, markdown) => {
            await createTemplate({ name, source_markdown: markdown });
          }}
          onUploadTemplateFile={async (name, file) => {
            await uploadTemplate(name, file);
          }}
          onUploadInstructions={async (name, file) => {
            await uploadInstructions(name, file);
          }}
          onRemoveTemplate={async (id) => {
            await removeTemplate(id);
          }}
          onRemoveInstructions={async (id) => {
            await removeInstructions(id);
          }}
        />
      ) : null}

      <MbRunNowModal
        open={runNowOpen}
        onClose={() => setRunNowOpen(false)}
        onStarted={(reportId) => setLiveReportId(reportId)}
      />

      {editorOpen ? (
        <ScheduleEditorModal
          schedule={editorSchedule}
          onClose={() => setEditorOpen(false)}
          onSave={handleSaveSchedule}
        />
      ) : null}

      <ConfirmDialog
        open={pendingRemoval !== null}
        title={t("morning_briefing.cabinet.remove_title")}
        description={t("morning_briefing.cabinet.remove_description")}
        confirmLabel={t("morning_briefing.cabinet.remove_confirm")}
        destructive
        onCancel={() => setPendingRemoval(null)}
        onConfirm={() => {
          const id = pendingRemoval;
          setPendingRemoval(null);
          if (!id) return;
          if (id === liveReportId) setLiveReportId(null);
          void removeReport(id);
        }}
      />
    </div>
  );
}
