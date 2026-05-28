/**
 * v3 equity-research page.
 *
 * Visual shape mirrors the v1/v2 equity-research surface — centered
 * WelcomeStage greeting on first load, bottom-pinned ErComposer for
 * free-form prompts, the model picker pill in the composer toolbar,
 * and the Report Settings pill on the WelcomeStage row. Submission
 * goes through the SSE start endpoint (``POST /v3/runs/start``) and
 * the stream lives inside ``useV3RunStream``.
 *
 * v3 takes a free-form ``subject`` (per schemas.py:111 — "either a
 * ticker (RKLB.US) or a free-form topic"), so the composer is in
 * single-textarea mode. No clarify stage; whatever the user types is
 * passed straight through as the subject for the run.
 *
 * The page also registers with ``useChatHeaderRegistry`` so the
 * global TopBar shows the same breadcrumb + history dropdown the
 * v1/v2 page does. Since v3 has no chat-session model, we plug a
 * v3-specific ``V3RunsPopover`` into the registry's ``renderPopover``
 * slot — each run row maps to its report_id.
 */
import { type JSX, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/_request";
import {
  type V3ReportDetail,
  type V3StartPayload,
  getV3Run,
  startV3Revision,
  startV3RunAsync,
} from "../../api/equity-research-v3";
import { useAuth } from "../../auth/AuthContext";
import { ErComposer } from "../../components/equity-research/ErComposer";
import { WelcomeStage } from "../../components/equity-research/WelcomeStage";
import {
  V3ChatThread,
  type ChatSettingsSnapshot,
} from "../../components/equity-research-v3/V3ChatThread";
import {
  V3ModelPicker,
  type V3ModelSelection,
} from "../../components/equity-research-v3/V3ModelPicker";
import {
  V3ReportSettingsModal,
  type V3SettingsValue,
} from "../../components/equity-research-v3/V3ReportSettingsModal";
import { V3RunsPopover } from "../../components/equity-research-v3/V3RunsPopover";
import { V3TemplateUploadModal } from "../../components/equity-research-v3/V3TemplateUploadModal";
import { useV3RunStream } from "../../components/equity-research-v3/useV3RunStream";
import { useChatHeaderRegistry } from "../../layouts/ChatHeaderContext";

const SETTINGS_LS_KEY = "er.v3.settings";

const DEFAULT_SETTINGS: V3SettingsValue = {
  length: "normal",
  language: "en",
  reasoningEffort: "medium",
  // The seeded built-in for initiation reports. The picker is the
  // only place templates change, so this default is what new users
  // see on the WelcomeStage pill before opening settings.
  templateId: "initiation_default",
  templateName: "Stock Initiation",
};

function loadSettings(): V3SettingsValue {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    const raw = window.localStorage.getItem(SETTINGS_LS_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    const parsed = JSON.parse(raw) as Partial<V3SettingsValue>;
    return {
      length: parsed.length ?? DEFAULT_SETTINGS.length,
      language: parsed.language ?? DEFAULT_SETTINGS.language,
      reasoningEffort:
        parsed.reasoningEffort ?? DEFAULT_SETTINGS.reasoningEffort,
      templateId: parsed.templateId ?? DEFAULT_SETTINGS.templateId,
      templateName: parsed.templateName ?? DEFAULT_SETTINGS.templateName,
    };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

function saveSettings(next: V3SettingsValue): void {
  try {
    window.localStorage.setItem(SETTINGS_LS_KEY, JSON.stringify(next));
  } catch {
    /* localStorage disabled — settings still apply for this session. */
  }
}

function firstName(displayName: string | null | undefined): string {
  if (!displayName) return "there";
  const trimmed = displayName.trim();
  if (!trimmed) return "there";
  return trimmed.split(/\s+/)[0];
}

// The shared WelcomeStage/ErComposer chrome still requires a
// ``mode: ReportMode`` prop for v1/v2 callers. v3 doesn't track
// report type as a separate concept (templates ARE the report type),
// so the pill label comes from ``templateLabel`` and ``mode`` is set
// to a safe constant.
const V3_MODE_FOR_SHARED_CHROME = "stock_initiation" as const;

export default function EquityResearchV3(): JSX.Element {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const reportIdFromUrl = searchParams.get("id") ?? null;

  const [prompt, setPrompt] = useState("");
  const [settings, setSettings] = useState<V3SettingsValue>(() => loadSettings());
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [model, setModel] = useState<V3ModelSelection | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [templatesRefreshKey, setTemplatesRefreshKey] = useState(0);

  const [startError, setStartError] = useState<string | null>(null);
  const [detail, setDetail] = useState<V3ReportDetail | null>(null);
  const [activeReportId, setActiveReportId] = useState<string | null>(reportIdFromUrl);
  // Keep the active run's subject so the TopBar breadcrumb can render
  // it as a chat-title equivalent. Updated when the page learns the
  // subject (either fresh dispatch or detail fetch).
  const [activeSubject, setActiveSubject] = useState<string | null>(null);
  // Snapshot of the initial prompt + settings the user submitted.
  // Held in memory so the first chat message renders the chips
  // accurately even before ``detail`` arrives, and so we don't lose
  // ``reasoning_effort`` (which isn't persisted on the row today).
  // Cleared on new-chat; resets to null on page reload (the chat
  // thread falls back to ``detail.report`` fields for the chips).
  const [initialPrompt, setInitialPrompt] = useState<string | null>(null);
  const [initialSettings, setInitialSettings] =
    useState<ChatSettingsSnapshot | null>(null);
  // Revisions in flight: set true on submit so the bottom composer
  // disables until the revision lands terminal. The chat thread
  // polls and re-fetches detail; we flip back on the same callback.
  const [revisionInFlight, setRevisionInFlight] = useState(false);

  const stream = useV3RunStream(activeReportId);

  const persistSettings = useCallback((next: V3SettingsValue) => {
    setSettings(next);
    saveSettings(next);
  }, []);

  // When the stream reaches a terminal state, fetch the persisted
  // detail so the result viewer renders sections + bibliography.
  // Also fires for late-connect runs (?id= with snapshot).
  useEffect(() => {
    if (!activeReportId) {
      setDetail(null);
      setActiveSubject(null);
      return;
    }
    if (stream.status !== "streaming" && stream.status !== "idle") {
      let cancelled = false;
      (async () => {
        try {
          const d = await getV3Run(activeReportId);
          if (!cancelled) {
            setDetail(d);
            setActiveSubject(d.report.subject);
          }
        } catch (err) {
          if (cancelled) return;
          setStartError(err instanceof Error ? err.message : String(err));
        }
      })();
      return () => {
        cancelled = true;
      };
    }
  }, [activeReportId, stream.status]);

  // Keep ?id= in the URL synced to whichever run we're watching.
  useEffect(() => {
    if (activeReportId && activeReportId !== reportIdFromUrl) {
      setSearchParams({ id: activeReportId }, { replace: true });
    }
  }, [activeReportId, reportIdFromUrl, setSearchParams]);

  const isStreaming = stream.status === "streaming";
  // A revision can only be submitted against a completed report.
  // While the initial run is streaming, or while a revision is in
  // flight, the bottom composer dispatches nothing.
  const canRevise =
    detail !== null
    && !isStreaming
    && !revisionInFlight
    && detail.report.status !== "running"
    && detail.report.status !== "failed";

  const refreshDetail = useCallback(async () => {
    if (!activeReportId) return;
    try {
      const d = await getV3Run(activeReportId);
      setDetail(d);
      setRevisionInFlight(false);
    } catch (err) {
      setStartError(err instanceof Error ? err.message : String(err));
      setRevisionInFlight(false);
    }
  }, [activeReportId]);

  const handleSubmit = useCallback(
    async (payload: { ticker: string; prompt: string }) => {
      const text = payload.prompt.trim();
      if (!text) {
        setStartError("Tell the engine what to research.");
        return;
      }

      // ----- Revision branch: there's an active completed report -----
      if (canRevise && activeReportId) {
        setStartError(null);
        setPrompt("");
        setRevisionInFlight(true);
        try {
          await startV3Revision(activeReportId, { request: text });
          // V3ChatThread polls listV3Revisions and fires
          // ``refreshDetail`` once the latest revision lands
          // terminal; that resets ``revisionInFlight``.
        } catch (err) {
          setRevisionInFlight(false);
          if (err instanceof ApiError && err.status === 409) {
            setStartError(
              "Another revision is already in flight. Wait for it to finish or cancel it.",
            );
          } else {
            setStartError(err instanceof Error ? err.message : String(err));
          }
        }
        return;
      }

      // ----- Original-run branch ------------------------------------
      if (!model) {
        setStartError("No model selected. Configure one in Settings → Models.");
        return;
      }
      setStartError(null);
      setDetail(null);
      setPrompt("");
      setActiveSubject(text);
      setInitialPrompt(text);
      setInitialSettings({
        templateName: settings.templateName,
        length: settings.length,
        language: settings.language,
        reasoningEffort: settings.reasoningEffort,
        modelLabel: model.display_name,
      });
      try {
        const body: V3StartPayload = {
          subject: text,
          language: settings.language,
          length: settings.length,
          // template_id is the single source of truth — v3 doesn't
          // ship a separate report_type concept anymore. Built-ins
          // (initiation_default etc.) and user uploads both resolve
          // through the same path.
          template_id: settings.templateId,
          provider_kind: model.provider_kind,
          model: model.model,
          // Wire enum is "medium" | "high" only; off → null so the
          // server's ReasoningEffort field stays None and the
          // adapter skips the reasoning param entirely.
          reasoning_effort:
            settings.reasoningEffort === "off" ? null : settings.reasoningEffort,
        };
        const response = await startV3RunAsync(body);
        setActiveReportId(response.report_id);
      } catch (err) {
        if (err instanceof ApiError && err.status === 503) {
          setStartError(
            "v3 engine disabled on the server. Set REPORT_ENGINE_VERSION=v3 to enable.",
          );
        } else {
          setStartError(err instanceof Error ? err.message : String(err));
        }
      }
    },
    [
      activeReportId,
      canRevise,
      model,
      settings.language,
      settings.length,
      settings.reasoningEffort,
      settings.templateId,
      settings.templateName,
    ],
  );

  const handleStop = useCallback(() => {
    if (isStreaming) void stream.cancel();
  }, [isStreaming, stream]);

  const handleNewRun = useCallback(() => {
    setActiveReportId(null);
    setDetail(null);
    setActiveSubject(null);
    setInitialPrompt(null);
    setInitialSettings(null);
    setRevisionInFlight(false);
    setStartError(null);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("id");
        return next;
      },
      { replace: true },
    );
  }, [setSearchParams]);

  const handleSelectRun = useCallback(
    (runId: string) => {
      if (runId === activeReportId) return;
      setActiveReportId(runId);
      setDetail(null);
      setActiveSubject(null);
      // Picking a run from history loads it fresh — the chips
      // fall back to ``detail.report`` fields since we don't have
      // the original in-memory settings snapshot.
      setInitialPrompt(null);
      setInitialSettings(null);
      setRevisionInFlight(false);
      setStartError(null);
    },
    [activeReportId],
  );

  // Reach for ?id= on first paint when present, so the dropdown row
  // for a freshly-loaded URL shows up highlighted. We don't need a
  // separate effect because `activeReportId` is already seeded from
  // reportIdFromUrl above; this is just a no-op safety guard.

  // Register the chat-header so the global TopBar renders the v3
  // history dropdown + "New chat" button. The renderPopover slot
  // plugs the v3-specific runs list in; TopBar stays generic.
  const { register, clear } = useChatHeaderRegistry();
  useEffect(() => {
    register({
      departmentId: "equity_research_v3",
      activeSessionId: activeReportId,
      chatTitle: activeSubject ?? "New chat",
      onSelect: handleSelectRun,
      onCreate: handleNewRun,
      renderPopover: (props) => (
        <V3RunsPopover
          activeSessionId={props.activeSessionId}
          onSelect={props.onSelect}
          onActiveDeleted={props.onActiveDeleted}
          onClose={props.onClose}
        />
      ),
    });
    return () => clear();
  }, [
    activeReportId,
    activeSubject,
    clear,
    handleNewRun,
    handleSelectRun,
    register,
  ]);

  const isWelcome = activeReportId === null && detail === null && !isStreaming;
  const placeholder = isWelcome
    ? 'What should this report cover? (e.g., "RKLB.US — initiation, focus on launch cadence")'
    : canRevise
      ? "Ask a follow-up or describe a revision…"
      : revisionInFlight
        ? "Revision in flight…"
        : isStreaming
          ? "Run in progress…"
          : "New report…";

  return (
    <div
      className="flex h-full flex-col bg-[--color-bg-base]"
      data-testid="er-v3-page"
    >
      <div className="flex flex-1 min-h-0 flex-col">
        <div className="flex flex-1 min-h-0 flex-col overflow-y-auto">
          {isWelcome ? (
            <WelcomeStage
              firstName={firstName(user?.display_name)}
              mode={V3_MODE_FOR_SHARED_CHROME}
              length={settings.length}
              onModeRowClick={() => setSettingsOpen(true)}
              templateLabel={settings.templateName}
            />
          ) : (
            <div className="flex w-full flex-col gap-4 px-6 py-6">
              <V3ChatThread
                initialPrompt={initialPrompt}
                initialSettings={initialSettings}
                reportId={activeReportId}
                stream={{
                  status: stream.status,
                  events: stream.events,
                  sectionsWritten: stream.sectionsWritten,
                  chartsEmitted: stream.chartsEmitted,
                  toolCallsInflight: stream.toolCallsInflight,
                  terminalMessage: stream.terminalMessage,
                  errorMessage: stream.errorMessage,
                }}
                detail={detail}
                onRefreshDetail={refreshDetail}
              />
            </div>
          )}
        </div>

        {startError ? (
          <div className="flex-shrink-0 border-t border-[--color-border-subtle] bg-[--color-bg-base] px-6 pt-3">
            <div
              role="alert"
              data-testid="er-v3-error"
              className="mx-auto max-w-[760px] rounded-md border border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] px-3 py-2 text-[12px] text-[--color-feedback-danger]"
            >
              {startError}
            </div>
          </div>
        ) : null}
      </div>

      <ErComposer
        value={prompt}
        onChange={setPrompt}
        onSubmit={handleSubmit}
        onStop={handleStop}
        isStreaming={isStreaming}
        placeholder={placeholder}
        mode={V3_MODE_FOR_SHARED_CHROME}
        length={settings.length}
        onModeClick={() => setSettingsOpen(true)}
        modelPicker={<V3ModelPicker onChange={setModel} />}
        // Lock the composer while the initial run is mid-stream or a
        // revision is in flight — those are the only states where
        // we have no useful place to dispatch the typed text. A new
        // run still requires a model selection.
        disabled={
          (model === null && !canRevise) || revisionInFlight
          || (isStreaming && !canRevise)
        }
        templateLabel={settings.templateName}
      />

      <V3ReportSettingsModal
        open={settingsOpen}
        value={settings}
        onClose={() => setSettingsOpen(false)}
        onSave={persistSettings}
        onUploadClick={() => {
          setSettingsOpen(false);
          setUploadOpen(true);
        }}
        templatesRefreshKey={templatesRefreshKey}
      />

      <V3TemplateUploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onSaved={(created) => {
          // Auto-select the newly uploaded template + reopen settings
          // so the user sees their pick land in the list.
          persistSettings({
            ...settings,
            templateId: created.id,
            templateName: created.name,
          });
          setTemplatesRefreshKey((k) => k + 1);
          setSettingsOpen(true);
        }}
      />
    </div>
  );
}

