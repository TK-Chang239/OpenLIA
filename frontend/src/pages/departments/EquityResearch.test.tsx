import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { MemoryRouter } from "react-router-dom";

import EquityResearch from "./EquityResearch";
import { FileViewerProvider } from "../../components/viewer/FileViewerContext";

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

vi.mock("../../api/chat", () => ({
  createSession: vi.fn().mockResolvedValue({ id: "sess-1" }),
  listMessages: vi.fn().mockResolvedValue({ items: [] }),
}));

vi.mock("../../api/reports", async () => {
  const actual = await vi.importActual<typeof import("../../api/reports")>(
    "../../api/reports",
  );
  return {
    ...actual,
    fetchReport: vi.fn().mockResolvedValue({
      schema_version: "1.0",
      department: "equity_research",
      generated_at: "2026-04-24T00:00:00Z",
      cover: { title: "AAPL Initiation", subtitle: "x", tagline: "Strong" },
      sections: [],
    }),
  };
});

const renderPage = () =>
  render(
    <MemoryRouter>
      <FileViewerProvider>
        <EquityResearch />
      </FileViewerProvider>
    </MemoryRouter>,
  );

/**
 * Encode an SSE response body from `event:`/`data:` frames so the
 * report-stream / chat-stream consumers parse them correctly.
 */
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

describe("EquityResearchPage", () => {
  it("renders welcome state heading and chips", () => {
    renderPage();
    const headings = screen.getAllByRole("heading", { name: /equity research/i });
    expect(headings.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: "AAPL" })).toBeInTheDocument();
  });

  it("pre-fills the input from the ?ticker= query param (NEW-21-09)", () => {
    render(
      <MemoryRouter initialEntries={["/equity-research?ticker=NVDA"]}>
        <FileViewerProvider>
          <EquityResearch />
        </FileViewerProvider>
      </MemoryRouter>,
    );
    const textarea = screen.getByPlaceholderText(/Enter a ticker/i) as HTMLTextAreaElement;
    expect(textarea.value).toBe("NVDA");
  });

  it("Report Settings button opens the modal", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /report settings/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("clicking a chip auto-submits the /report POST exactly once (NEW-14-03)", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      body: sseBody([]),
    }) as unknown as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    renderPage();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "TSLA" }));
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
    expect(reportCall).toBeDefined();
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
      fireEvent.click(screen.getByRole("button", { name: "AAPL" }));
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
        {
          event: "report.error",
          data: { report_id: "r_42", message: "boom" },
        },
      ]),
    }) as unknown as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    renderPage();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "AAPL" }));
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
      fireEvent.click(screen.getByRole("button", { name: "AAPL" }));
    });

    await waitFor(() => {
      expect(screen.getByTestId("er-report-card")).toBeInTheDocument();
    });

    const chatInput = await screen.findByRole("textbox");
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
