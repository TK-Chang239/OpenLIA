/**
 * Phase 12 NEW-12-21 — Targeted vitest gap-fillers.
 *
 * Each describe block addresses one specific behaviour mentioned in the
 * fix-plan acceptance: CodeRenderer fallback, CsvRenderer header sticky,
 * ImageRenderer lightbox, UnsupportedRenderer link, UserBubble truncation,
 * ThinkingIndicator aria-live, ToolCallChip transitions, ErrorMessage retry,
 * ReportThumbnail kindFromFilename, useFileViewer guard, drawer department
 * swap reset.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { CodeRenderer } from "../../viewer/renderers/CodeRenderer";
import { CsvRenderer } from "../../viewer/renderers/CsvRenderer";
import { ImageRenderer } from "../../viewer/renderers/ImageRenderer";
import { UnsupportedRenderer } from "../../viewer/renderers/UnsupportedRenderer";
import { UserBubble } from "../UserBubble";
import { ThinkingIndicator } from "../ThinkingIndicator";
import { ToolCallChip } from "../ToolCallChip";
import { ErrorMessage } from "../ErrorMessage";
import { ReportThumbnail } from "../ReportThumbnail";
import { useFileViewer, kindFromFilename } from "../../viewer/FileViewerContext";
import { ChatHistoryDrawer } from "../ChatHistoryDrawer";
import * as chatApi from "../../../api/chat";

function mockFetchText(body: string, ok = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok,
      status: ok ? 200 : 500,
      text: async () => body,
    }),
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("Phase 12 targeted gaps", () => {
  it("CodeRenderer falls back to language-text when no language hint", async () => {
    mockFetchText("alpha");
    render(<CodeRenderer source={{ kind: "attachment", attachmentId: "1" }} />);
    await waitFor(() => expect(screen.getByText(/alpha/)).toBeInTheDocument());
    const code = document.querySelector("code.language-text");
    expect(code).toBeTruthy();
  });

  it("CsvRenderer keeps the header row sticky", async () => {
    mockFetchText("a,b\n1,2");
    render(<CsvRenderer source={{ kind: "attachment", attachmentId: "2" }} />);
    await waitFor(() => expect(screen.getByText("a")).toBeInTheDocument());
    const thead = document.querySelector("thead");
    expect(thead?.className).toMatch(/sticky/);
  });

  it("ImageRenderer toggles a lightbox class on click", () => {
    render(<ImageRenderer source={{ kind: "attachment", attachmentId: "7" }} />);
    const button = screen.getByRole("button", { name: /zoom image/i });
    fireEvent.click(button);
    expect(
      screen.getByRole("button", { name: /close zoomed image/i }),
    ).toBeInTheDocument();
  });

  it("UnsupportedRenderer surfaces a download link", () => {
    render(
      <UnsupportedRenderer
        source={{ kind: "attachment", attachmentId: "5" }}
        filename="bin.exe"
      />,
    );
    expect(
      screen.getByRole("link", { name: /download the file to view it/i }),
    ).toHaveAttribute("href", "/api/chat/attachments/5/download");
  });

  it("UserBubble caps width via max-w (truncation guard)", () => {
    render(<UserBubble content={"x".repeat(2000)} />);
    const bubble = document.querySelector(
      '[role="article"] > div',
    ) as HTMLDivElement;
    expect(bubble.className).toMatch(/max-w-\[520px\]/);
  });

  it("ThinkingIndicator announces via aria-live=polite", () => {
    render(<ThinkingIndicator />);
    const status = screen.getByRole("status");
    expect(status.getAttribute("aria-live")).toBe("polite");
  });

  it("ToolCallChip transitions running label → done summary", () => {
    const { rerender } = render(
      <ToolCallChip
        toolName="get_quote"
        argsPreview="AAPL"
        status="running"
      />,
    );
    expect(screen.getByText(/market data — aapl/i)).toBeInTheDocument();
    rerender(
      <ToolCallChip
        toolName="get_quote"
        argsPreview="AAPL"
        status="done"
        summary="Got AAPL"
      />,
    );
    expect(screen.getByText("Got AAPL")).toBeInTheDocument();
  });

  it("ErrorMessage dispatches onRetry when 'Try again' is clicked", () => {
    const onRetry = vi.fn();
    render(<ErrorMessage message="Boom" onRetry={onRetry} />);
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("ReportThumbnail uses kindFromFilename for the icon hint", () => {
    expect(kindFromFilename("a.pdf")).toBe("pdf");
    expect(kindFromFilename("a.csv")).toBe("csv");
    expect(kindFromFilename("a.md")).toBe("markdown");
    // Component renders without throwing for known kinds.
    const Wrapped = () => (
      <RequireProvider>
        <ReportThumbnail reportId="r1" filename="a.pdf" />
      </RequireProvider>
    );
    render(<Wrapped />);
    expect(
      screen.getByRole("group", { name: /attachment: a.pdf/i }),
    ).toBeInTheDocument();
  });

  it("useFileViewer throws when the provider is absent", () => {
    function GuardConsumer() {
      useFileViewer();
      return <span>ok</span>;
    }
    expect(() => render(<GuardConsumer />)).toThrow(
      /requires FileViewerProvider/,
    );
  });

  it("ChatHistoryDrawer resets the list on department prop change", async () => {
    const spy = vi.spyOn(chatApi, "listSessions");
    spy.mockResolvedValueOnce({
      items: [
        {
          id: "00000000-0000-4000-8000-000000000010",
          department: "secretary",
          title: "secretary chat",
          is_pinned: false,
          is_archived: false,
          created_at: "2026-04-01T00:00:00Z",
        },
      ],
    });
    spy.mockResolvedValueOnce({
      items: [
        {
          id: "00000000-0000-4000-8000-000000000011",
          department: "morning_briefing",
          title: "mb chat",
          is_pinned: false,
          is_archived: false,
          created_at: "2026-04-01T00:00:00Z",
        },
      ],
    });
    const { rerender } = render(
      <ChatHistoryDrawer
        department="secretary"
        activeSessionId={null}
        onSelect={() => {}}
        onCreate={() => {}}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText("secretary chat")).toBeInTheDocument(),
    );
    rerender(
      <ChatHistoryDrawer
        department="morning_briefing"
        activeSessionId={null}
        onSelect={() => {}}
        onCreate={() => {}}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText("mb chat")).toBeInTheDocument(),
    );
    expect(screen.queryByText("secretary chat")).toBeNull();
    // listSessions called with the new department.
    const lastCall = spy.mock.calls[spy.mock.calls.length - 1][0];
    expect(lastCall).toMatchObject({ department: "morning_briefing" });
  });
});

import { FileViewerProvider } from "../../viewer/FileViewerContext";
function RequireProvider({ children }: { children: React.ReactNode }) {
  return <FileViewerProvider>{children}</FileViewerProvider>;
}
