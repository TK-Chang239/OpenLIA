import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChatHistoryList } from "../ChatHistoryList";

const listSessions = vi.fn();
const deleteSession = vi.fn();
const patchSession = vi.fn();

vi.mock("../../../api/chat", async () => {
  const actual: Record<string, unknown> = await vi.importActual("../../../api/chat");
  return {
    ...actual,
    listSessions: (...args: unknown[]) => listSessions(...args),
    deleteSession: (...args: unknown[]) => deleteSession(...args),
    patchSession: (...args: unknown[]) => patchSession(...args),
    createSession: vi.fn(),
  };
});

const session = (over: Partial<Record<string, unknown>>) => ({
  id: "s1",
  department: "secretary",
  title: "session 1",
  is_pinned: false,
  is_archived: false,
  created_at: "2026-05-04T00:00:00Z",
  model_id: null,
  ...over,
});

const reportsById = {
  r_msft: { id: "r_msft", title: "MSFT Initiation Report", department: "equity_research", report_type: "initiation", created_at: "2026-05-01T00:00:00Z" },
};

describe("ChatHistoryList", () => {
  beforeEach(() => {
    listSessions.mockReset();
    deleteSession.mockReset().mockResolvedValue(undefined);
    patchSession.mockReset().mockResolvedValue({ ok: true });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("invokes onActiveDeleted when the active session is deleted", async () => {
    listSessions.mockResolvedValue({ items: [session({ id: "active", title: "Active one" })] });
    const onSelect = vi.fn();
    const onActiveDeleted = vi.fn();
    render(
      <ChatHistoryList
        department="secretary"
        activeSessionId="active"
        onSelect={onSelect}
        onActiveDeleted={onActiveDeleted}
      />,
    );
    await screen.findByText("Active one");
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /^delete$/i }));
    await waitFor(() => expect(deleteSession).toHaveBeenCalledWith("active"));
    expect(onActiveDeleted).toHaveBeenCalledWith("active");
  });

  it("does not invoke onActiveDeleted when a different session is deleted", async () => {
    listSessions.mockResolvedValue({
      items: [
        session({ id: "active", title: "Active" }),
        session({ id: "other", title: "Other" }),
      ],
    });
    const onActiveDeleted = vi.fn();
    render(
      <ChatHistoryList
        department="secretary"
        activeSessionId="active"
        onSelect={() => undefined}
        onActiveDeleted={onActiveDeleted}
      />,
    );
    await screen.findByText("Other");
    const deletes = screen.getAllByRole("button", { name: "Delete" });
    fireEvent.click(deletes[1]);
    const dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /^delete$/i }));
    await waitFor(() => expect(deleteSession).toHaveBeenCalledWith("other"));
    expect(onActiveDeleted).not.toHaveBeenCalled();
  });

  it("shows 'Discussion: <report title>' for bound sessions; default title otherwise", async () => {
    listSessions.mockResolvedValue({
      items: [
        session({ id: "s1", title: "Equity Research", attached_report_id: null }),
        session({ id: "s2", title: null, attached_report_id: "r_msft" }),
      ],
    });
    render(
      <ChatHistoryList
        department="secretary"
        activeSessionId={null}
        onSelect={() => undefined}
        reportsById={reportsById as any}
      />,
    );
    await screen.findByText("Equity Research");
    expect(screen.getByText(/discussion: msft initiation report/i)).toBeInTheDocument();
  });

  it("shows the paperclip icon next to bound sessions only", async () => {
    listSessions.mockResolvedValue({
      items: [
        session({ id: "s1", title: "Equity Research", attached_report_id: null }),
        session({ id: "s2", title: null, attached_report_id: "r_msft" }),
      ],
    });
    render(
      <ChatHistoryList
        department="secretary"
        activeSessionId={null}
        onSelect={() => undefined}
        reportsById={reportsById as any}
      />,
    );
    await screen.findByText("Equity Research");
    expect(screen.getAllByTestId("attached-report-icon")).toHaveLength(1);
  });
});
