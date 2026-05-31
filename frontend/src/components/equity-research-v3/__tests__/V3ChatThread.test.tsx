import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import type {
  V3ReportDetail,
  V3Revision,
} from "../../../api/equity-research-v3";
import { V3ChatThread, type ChatSettingsSnapshot } from "../V3ChatThread";

vi.mock("../../../api/equity-research-v3", async () => {
  const actual = await vi.importActual<
    typeof import("../../../api/equity-research-v3")
  >("../../../api/equity-research-v3");
  return {
    ...actual,
    listV3Revisions: vi.fn(),
    cancelV3Revision: vi.fn(),
  };
});

const { listV3Revisions } = await import("../../../api/equity-research-v3");
const listV3RevisionsMock = listV3Revisions as ReturnType<typeof vi.fn>;

const SETTINGS: ChatSettingsSnapshot = {
  templateName: "Stock Initiation",
  length: "normal",
  language: "en",
  reasoningEffort: "medium",
  modelLabel: "Claude Sonnet 4.6",
};

const DETAIL: V3ReportDetail = {
  report: {
    report_id: "rep-1",
    subject: "RKLB.US — initiation",
    template_id: "initiation_default",
    language: "en",
    length: "normal",
    status: "completed",
    created_at: "2026-05-28T10:00:00Z",
    completed_at: "2026-05-28T10:05:00Z",
  },
  error_message: null,
  sections: [
    {
      section_id: "overview",
      section_index: 0,
      title: "Overview",
      markdown: "Overview body.",
      version: 1,
    },
  ],
  charts: [],
  citations: [],
};

const EMPTY_STREAM = {
  status: "idle",
  events: [] as never[],
  sectionsWritten: 0,
  chartsEmitted: 0,
  citationsSeen: 0,
  elapsedSeconds: null as number | null,
  toolCallsInflight: 0,
  terminalMessage: null as string | null,
  errorMessage: null as string | null,
};

const originalScrollIntoView = Element.prototype.scrollIntoView;

beforeEach(() => {
  vi.clearAllMocks();
  listV3RevisionsMock.mockResolvedValue([]);
  // jsdom doesn't implement scrollIntoView; stub it so the
  // component's auto-scroll effect doesn't blow up the test.
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  Element.prototype.scrollIntoView = originalScrollIntoView;
});

describe("V3ChatThread — initial turn", () => {
  test("renders the initial user message with prompt + settings chips", async () => {
    render(
      <V3ChatThread
        initialPrompt="Research RKLB.US — focus on Neutron"
        initialSettings={SETTINGS}
        reportId="rep-1"
        stream={EMPTY_STREAM}
        detail={DETAIL}
        onRefreshDetail={() => {}}
      />,
    );
    await waitFor(() => expect(listV3RevisionsMock).toHaveBeenCalled());
    const messages = screen.getAllByTestId("er-v3-user-message");
    expect(messages).toHaveLength(1);
    expect(messages[0]).toHaveTextContent(/Research RKLB.US/);
    const chips = screen.getByTestId("er-v3-settings-chips");
    expect(chips).toHaveTextContent(/Stock Initiation/);
    expect(chips).toHaveTextContent(/Normal/);
    expect(chips).toHaveTextContent(/English/);
    expect(chips).toHaveTextContent(/Medium/);
    expect(chips).toHaveTextContent(/Claude Sonnet 4.6/);
  });

  test("falls back to detail.report.subject when initialPrompt is null (page reload)", async () => {
    render(
      <V3ChatThread
        initialPrompt={null}
        initialSettings={null}
        reportId="rep-1"
        stream={EMPTY_STREAM}
        detail={DETAIL}
        onRefreshDetail={() => {}}
      />,
    );
    const messages = await screen.findAllByTestId("er-v3-user-message");
    expect(messages[0]).toHaveTextContent("RKLB.US — initiation");
    // Falls back to a derived snapshot from detail.report; chips
    // still render (no reasoning / model since those aren't on the row).
    expect(screen.getByTestId("er-v3-settings-chips")).toHaveTextContent(
      /Stock Initiation/,
    );
  });

  test("Reasoning chip surfaces on page reload when report.reasoning_effort is persisted", async () => {
    render(
      <V3ChatThread
        initialPrompt={null}
        initialSettings={null}
        reportId="rep-1"
        stream={EMPTY_STREAM}
        detail={{
          ...DETAIL,
          report: { ...DETAIL.report, reasoning_effort: "high" },
        }}
        onRefreshDetail={() => {}}
      />,
    );
    const chips = await screen.findByTestId("er-v3-settings-chips");
    expect(chips).toHaveTextContent(/Reasoning/);
    expect(chips).toHaveTextContent(/High/);
  });

  test("Reasoning chip is omitted on page reload when reasoning was off", async () => {
    render(
      <V3ChatThread
        initialPrompt={null}
        initialSettings={null}
        reportId="rep-1"
        stream={EMPTY_STREAM}
        detail={{
          ...DETAIL,
          report: { ...DETAIL.report, reasoning_effort: null },
        }}
        onRefreshDetail={() => {}}
      />,
    );
    const chips = await screen.findByTestId("er-v3-settings-chips");
    expect(chips).not.toHaveTextContent(/Reasoning/);
  });

  test("renders the generating report card while the run streams", async () => {
    render(
      <V3ChatThread
        initialPrompt="Initiate coverage on AAPL"
        initialSettings={{
          templateName: "Stock Initiation",
          length: "normal",
          language: "en",
          reasoningEffort: "medium",
          modelLabel: "Claude Sonnet",
        }}
        reportId="run-1"
        stream={{
          status: "streaming",
          events: [],
          sectionsWritten: 2,
          chartsEmitted: 0,
          citationsSeen: 1,
          elapsedSeconds: 4.2,
          toolCallsInflight: 1,
          terminalMessage: null,
          errorMessage: null,
        }}
        detail={null}
        onRefreshDetail={() => undefined}
      />,
    );
    expect(
      screen.getByTestId("er-v3-report-card-generating"),
    ).toBeInTheDocument();
    // Subject renders in both the user turn and the generating card.
    expect(
      screen.getAllByText("Initiate coverage on AAPL").length,
    ).toBeGreaterThan(0);
  });

  test("renders V3ReportCard once detail is present", async () => {
    render(
      <V3ChatThread
        initialPrompt="Research RKLB.US"
        initialSettings={SETTINGS}
        reportId="rep-1"
        stream={EMPTY_STREAM}
        detail={DETAIL}
        onRefreshDetail={() => {}}
      />,
    );
    expect(
      await screen.findByTestId("er-v3-report-card"),
    ).toBeInTheDocument();
  });
});

describe("V3ChatThread — revision turns", () => {
  test("renders each revision as a user turn + status badge", async () => {
    const revisions: V3Revision[] = [
      {
        id: "rev-1",
        report_id: "rep-1",
        revision_index: 1,
        request: "rewrite the bull case to lead with EBITDA margin",
        status: "completed",
        error_message: null,
        created_at: "2026-05-28T11:00:00Z",
        completed_at: "2026-05-28T11:05:00Z",
      },
      {
        id: "rev-2",
        report_id: "rep-1",
        revision_index: 2,
        request: "add a competitor analysis section",
        status: "running",
        error_message: null,
        created_at: "2026-05-28T11:10:00Z",
        completed_at: null,
      },
    ];
    listV3RevisionsMock.mockResolvedValueOnce(revisions);

    render(
      <V3ChatThread
        initialPrompt="Research RKLB.US"
        initialSettings={SETTINGS}
        reportId="rep-1"
        stream={EMPTY_STREAM}
        detail={DETAIL}
        onRefreshDetail={() => {}}
      />,
    );
    // Wait for the polled list to land.
    await waitFor(() => {
      expect(screen.getByTestId("er-v3-revision-turn-rev-1")).toBeInTheDocument();
    });
    expect(
      screen.getByTestId("er-v3-revision-turn-rev-2"),
    ).toBeInTheDocument();
    // Three user messages: the initial + the two revisions.
    expect(screen.getAllByTestId("er-v3-user-message")).toHaveLength(3);
    expect(screen.getByTestId("er-v3-revision-turn-rev-2")).toHaveTextContent(
      /Running/i,
    );
    expect(screen.getByTestId("er-v3-revision-turn-rev-1")).toHaveTextContent(
      /Completed/i,
    );
  });

  test("fires onRefreshDetail when a revision flips from running to terminal", async () => {
    const onRefresh = vi.fn();
    const running: V3Revision = {
      id: "rev-1",
      report_id: "rep-1",
      revision_index: 1,
      request: "x",
      status: "running",
      error_message: null,
      created_at: "2026-05-28T11:00:00Z",
      completed_at: null,
    };
    const completed: V3Revision = { ...running, status: "completed" };
    listV3RevisionsMock
      .mockResolvedValueOnce([running])
      .mockResolvedValueOnce([completed]);

    vi.useFakeTimers();
    render(
      <V3ChatThread
        initialPrompt="Research RKLB.US"
        initialSettings={SETTINGS}
        reportId="rep-1"
        stream={EMPTY_STREAM}
        detail={DETAIL}
        onRefreshDetail={onRefresh}
      />,
    );
    // First poll resolves -> revision is running -> useEffect schedules
    // the interval. Advance time to fire the second poll.
    await vi.runOnlyPendingTimersAsync();
    await vi.advanceTimersByTimeAsync(2100);
    vi.useRealTimers();
    await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1));
  });

  test("reports null reportId by rendering nothing", () => {
    const { container } = render(
      <V3ChatThread
        initialPrompt={null}
        initialSettings={null}
        reportId={null}
        stream={EMPTY_STREAM}
        detail={null}
        onRefreshDetail={() => {}}
      />,
    );
    expect(container.firstChild).toBeNull();
  });
});

describe("V3ChatThread — auto-scroll", () => {
  test("renders the bottom sentinel marker for auto-scroll", async () => {
    render(
      <V3ChatThread
        initialPrompt="Research RKLB.US"
        initialSettings={SETTINGS}
        reportId="rep-1"
        stream={EMPTY_STREAM}
        detail={DETAIL}
        onRefreshDetail={() => {}}
      />,
    );
    expect(
      await screen.findByTestId("er-v3-chat-bottom"),
    ).toBeInTheDocument();
  });

  test("calls scrollIntoView on the bottom marker when revisions arrive", async () => {
    const scrollSpy = Element.prototype.scrollIntoView as unknown as ReturnType<
      typeof vi.fn
    >;
    const revisions: V3Revision[] = [
      {
        id: "rev-1",
        report_id: "rep-1",
        revision_index: 1,
        request: "follow-up",
        status: "completed",
        error_message: null,
        created_at: "2026-05-28T11:00:00Z",
        completed_at: "2026-05-28T11:05:00Z",
      },
    ];
    listV3RevisionsMock.mockResolvedValueOnce(revisions);
    render(
      <V3ChatThread
        initialPrompt="Research RKLB.US"
        initialSettings={SETTINGS}
        reportId="rep-1"
        stream={EMPTY_STREAM}
        detail={DETAIL}
        onRefreshDetail={() => {}}
      />,
    );
    await waitFor(() =>
      expect(screen.getByTestId("er-v3-revision-turn-rev-1")).toBeInTheDocument(),
    );
    // The scroll effect runs on every turn-signal change — at least
    // once for the initial mount, again when revisions land.
    expect(scrollSpy).toHaveBeenCalled();
  });
});
