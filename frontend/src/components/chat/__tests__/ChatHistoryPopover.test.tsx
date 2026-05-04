import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChatHistoryPopover } from "../ChatHistoryPopover";

const listSessions = vi.fn();
const deleteSession = vi.fn();

vi.mock("../../../api/chat", async () => {
  const actual: Record<string, unknown> = await vi.importActual("../../../api/chat");
  return {
    ...actual,
    listSessions: (...args: unknown[]) => listSessions(...args),
    deleteSession: (...args: unknown[]) => deleteSession(...args),
    patchSession: vi.fn().mockResolvedValue({ ok: true }),
    createSession: vi.fn(),
  };
});

describe("ChatHistoryPopover dismissal", () => {
  let onClose: ReturnType<typeof vi.fn>;
  let onSelect: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onClose = vi.fn();
    onSelect = vi.fn();
    listSessions.mockReset().mockResolvedValue({ items: [] });
    deleteSession.mockReset().mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("calls onClose when Escape is pressed", async () => {
    render(
      <ChatHistoryPopover
        departmentId="secretary"
        activeSessionId={null}
        onSelect={onSelect}
        onClose={onClose}
      />,
    );
    await screen.findByTestId("chat-history-popover");
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("calls onClose when a click lands outside the popover", async () => {
    render(
      <div>
        <button data-testid="outside">outside</button>
        <ChatHistoryPopover
          departmentId="secretary"
          activeSessionId={null}
          onSelect={onSelect}
          onClose={onClose}
        />
      </div>,
    );
    await screen.findByTestId("chat-history-popover");
    fireEvent.mouseDown(screen.getByTestId("outside"));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("does not call onClose when a click lands inside the popover", async () => {
    render(
      <ChatHistoryPopover
        departmentId="secretary"
        activeSessionId={null}
        onSelect={onSelect}
        onClose={onClose}
      />,
    );
    const node = await screen.findByTestId("chat-history-popover");
    fireEvent.mouseDown(node);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("calls onActiveDeleted when the active session is deleted from the list", async () => {
    listSessions.mockResolvedValue({
      items: [
        {
          id: "active",
          department: "secretary",
          title: "Today",
          is_pinned: false,
          is_archived: false,
          created_at: "2026-05-04T00:00:00Z",
          model_id: null,
        },
      ],
    });
    const onActiveDeleted = vi.fn();
    render(
      <ChatHistoryPopover
        departmentId="secretary"
        activeSessionId="active"
        onSelect={onSelect}
        onClose={onClose}
        onActiveDeleted={onActiveDeleted}
      />,
    );
    await screen.findByText("Today");
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /^delete$/i }));
    await waitFor(() => expect(onActiveDeleted).toHaveBeenCalledWith("active"));
  });
});
