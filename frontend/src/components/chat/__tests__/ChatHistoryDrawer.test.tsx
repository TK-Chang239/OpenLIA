import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ChatHistoryDrawer } from "../ChatHistoryDrawer";
import * as chatApi from "../../../api/chat";

const S1 = "00000000-0000-4000-8000-000000000001";
const S2 = "00000000-0000-4000-8000-000000000002";
const S9 = "00000000-0000-4000-8000-000000000009";

describe("ChatHistoryDrawer", () => {
  beforeEach(() => {
    vi.spyOn(chatApi, "listSessions").mockResolvedValue({
      items: [
        { id: S1, department: "secretary", title: "My pinned chat", is_pinned: true, is_archived: false, created_at: "2026-04-01T00:00:00Z" },
        { id: S2, department: "secretary", title: "My recent chat", is_pinned: false, is_archived: false, created_at: "2026-04-01T00:00:00Z" },
      ],
    });
  });

  it("renders pinned and recent sections", async () => {
    render(
      <ChatHistoryDrawer department="secretary" activeSessionId={null} onSelect={() => {}} onCreate={() => {}} />,
    );
    await waitFor(() => screen.getByText("My pinned chat"));
    expect(screen.getByText("My recent chat")).toBeInTheDocument();
    expect(screen.getByText("Pinned")).toBeInTheDocument();
    expect(screen.getByText("Recent")).toBeInTheDocument();
  });

  it("fires onSelect when a session is clicked", async () => {
    const onSelect = vi.fn();
    render(
      <ChatHistoryDrawer department="secretary" activeSessionId={null} onSelect={onSelect} onCreate={() => {}} />,
    );
    await waitFor(() => screen.getByText("My recent chat"));
    fireEvent.click(screen.getByText("My recent chat"));
    expect(onSelect).toHaveBeenCalledWith(S2);
  });

  it("creates a new session", async () => {
    const onCreate = vi.fn();
    vi.spyOn(chatApi, "createSession").mockResolvedValue({
      id: S9,
      department: "secretary",
      title: "New",
      is_pinned: false,
      is_archived: false,
      created_at: "2026-04-01T00:00:00Z",
    });
    render(
      <ChatHistoryDrawer department="secretary" activeSessionId={null} onSelect={() => {}} onCreate={onCreate} />,
    );
    await waitFor(() => screen.getByText("My recent chat"));
    fireEvent.click(screen.getByRole("button", { name: /new chat/i }));
    await waitFor(() => expect(onCreate).toHaveBeenCalledWith(S9));
  });
});
