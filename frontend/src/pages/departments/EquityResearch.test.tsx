import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { MemoryRouter } from "react-router-dom";

import EquityResearch from "./EquityResearch";
import { FileViewerProvider } from "../../components/viewer/FileViewerContext";

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({
    status: "authenticated",
    user: {
      id: "u1",
      email: "tk@example.com",
      display_name: "TK Chang",
      role: "user",
    },
    login: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  }),
}));

vi.mock("../../hooks/useErConfig", () => ({
  useErConfig: () => ({
    config: {
      report_mode: "stock_initiation",
      report_length: "normal",
      sections_by_mode: {
        stock_initiation: [],
        stock_update: [],
        sector_research: [],
      },
      custom_sections_by_mode: {
        stock_initiation: [],
        stock_update: [],
        sector_research: [],
      },
    },
    loading: false,
    patch: vi.fn().mockResolvedValue(undefined),
  }),
}));

vi.mock("../../api/chat", async () => {
  const actual =
    await vi.importActual<typeof import("../../api/chat")>("../../api/chat");
  return {
    ...actual,
    createSession: vi.fn().mockResolvedValue({
      id: "sess-1",
      department: "equity_research",
      title: "AAPL",
      is_pinned: false,
      is_archived: false,
      created_at: "2026-04-29T00:00:00Z",
    }),
    getSession: vi.fn().mockResolvedValue({
      id: "sess-1",
      department: "equity_research",
      title: "AAPL",
      is_pinned: false,
      is_archived: false,
      created_at: "2026-04-29T00:00:00Z",
    }),
    listMessages: vi.fn().mockResolvedValue({ items: [] }),
  };
});

vi.mock("../../api/reports", async () => {
  const actual = await vi.importActual<typeof import("../../api/reports")>(
    "../../api/reports",
  );
  return {
    ...actual,
    fetchReport: vi.fn().mockResolvedValue({
      schema_version: "2.0",
      department: "equity_research",
      generated_at: "2026-04-24T00:00:00Z",
      cover: { title: "AAPL · Apple Inc.", subtitle: "x", tagline: "Strong" },
      sections: [],
    }),
  };
});

const renderPage = (initialEntries: string[] = ["/equity-research"]) =>
  render(
    <MemoryRouter initialEntries={initialEntries}>
      <FileViewerProvider>
        <EquityResearch />
      </FileViewerProvider>
    </MemoryRouter>,
  );

function sseBody(frames: { event: string; data: unknown }[]): ReadableStream<Uint8Array> {
  const text = frames
    .map((f) => `event: ${f.event}\ndata: ${JSON.stringify(f.data)}\n\n`)
    .join("");
  const enc = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(enc.encode(text));
      controller.close();
    },
  });
}

let originalFetch: typeof fetch | undefined;

beforeEach(() => {
  originalFetch = globalThis.fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch as typeof fetch;
  vi.clearAllMocks();
});

function submitInput(value: string) {
  const ta = screen.getByPlaceholderText(/Enter a ticker/i) as HTMLTextAreaElement;
  fireEvent.change(ta, { target: { value } });
  fireEvent.keyDown(ta, { key: "Enter", code: "Enter" });
}

describe("EquityResearchPage", () => {
  it("renders the welcome stage when no session is active", () => {
    renderPage();
    expect(screen.getByTestId("er-welcome-stage")).toBeInTheDocument();
  });

  it("pre-fills the input from the ?ticker= query param (NEW-21-09)", () => {
    renderPage(["/equity-research?ticker=NVDA"]);
    const textarea = screen.getByPlaceholderText(/Enter a ticker/i) as HTMLTextAreaElement;
    expect(textarea.value).toBe("NVDA");
  });

  it("composer mode pill opens the report settings modal", () => {
    renderPage();
    const modeBtns = screen.getAllByRole("button", {
      name: /change report mode and length/i,
    });
    fireEvent.click(modeBtns[0]);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("typing a ticker and submitting fires the /report POST exactly once", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      body: sseBody([]),
    }) as unknown as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    renderPage();
    await act(async () => {
      submitInput("TSLA");
    });

    const calls = fetchMock.mock.calls as unknown as [string, RequestInit?][];
    await waitFor(() => {
      const reportCalls = calls.filter((c) =>
        String(c[0]).includes("/api/departments/equity-research/report"),
      );
      expect(reportCalls.length).toBe(1);
    });
    const reportCall = calls.find((c) =>
      String(c[0]).includes("/api/departments/equity-research/report"),
    );
    const body = JSON.parse(String(reportCall?.[1]?.body ?? "{}"));
    expect(body.user_input).toBe("TSLA");
    expect(body.session_id).toBe("sess-1");
  });

  it("renders ReportCard inline once the SSE happy path completes", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      body: sseBody([
        {
          event: "report.start",
          data: {
            report_id: "r_42",
            department: "equity_research",
            mode: "stock_initiation",
            section_titles: ["Overview"],
          },
        },
        { event: "report.complete", data: { report_id: "r_42", schema: {} } },
        { event: "report.saved", data: { report_id: "r_42" } },
      ]),
    }) as unknown as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    renderPage();
    await act(async () => {
      submitInput("AAPL");
    });

    await waitFor(
      () => {
        expect(screen.getByTestId("er-report-card")).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
    expect(screen.getByText(/stock initiation report/i)).toBeInTheDocument();
  });

  it("renders an error retry button when report stream errors", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      body: sseBody([
        { event: "report.error", data: { report_id: "r_42", message: "boom" } },
      ]),
    }) as unknown as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    renderPage();
    await act(async () => {
      submitInput("AAPL");
    });

    const retry = await screen.findByRole("button", { name: /try again/i });
    expect(retry).toBeInTheDocument();
  });

  it("follow-up chat hits the ER chat URL with session_id (NEW-14-01)", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (typeof url === "string" && url.includes("/report")) {
        return {
          ok: true,
          status: 200,
          body: sseBody([
            {
              event: "report.start",
              data: {
                report_id: "r_42",
                department: "equity_research",
                mode: "stock_initiation",
                section_titles: [],
              },
            },
            { event: "report.complete", data: { report_id: "r_42", schema: {} } },
            { event: "report.saved", data: { report_id: "r_42" } },
          ]),
        } as unknown as Response;
      }
      return {
        ok: true,
        status: 200,
        body: sseBody([
          { event: "chat.start", data: { message_id: "m1" } },
          { event: "chat.token", data: { text: "ok" } },
          { event: "chat.done", data: { message_id: "m1", stop_reason: "stop" } },
        ]),
      } as unknown as Response;
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    renderPage();
    await act(async () => {
      submitInput("AAPL");
    });

    await waitFor(() => {
      expect(screen.getByTestId("er-report-card")).toBeInTheDocument();
    });

    const chatInput = await screen.findByPlaceholderText(/follow-up question/i);
    fireEvent.change(chatInput, { target: { value: "Tell me more" } });
    fireEvent.keyDown(chatInput, { key: "Enter", code: "Enter" });

    await waitFor(() => {
      const calls = fetchMock.mock.calls as unknown as [string, RequestInit?][];
      const chatCalls = calls.filter((c) =>
        String(c[0]).includes("/api/departments/equity-research/chat"),
      );
      expect(chatCalls.length).toBe(1);
      const init = chatCalls[0]?.[1];
      const body = JSON.parse(String(init?.body ?? "{}"));
      expect(body.session_id).toBe("sess-1");
      expect(body.message).toBe("Tell me more");
    });
  });
});
