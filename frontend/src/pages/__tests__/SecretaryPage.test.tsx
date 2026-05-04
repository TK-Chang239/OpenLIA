import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../components/chat/ChatInterface", () => ({
  ChatInterface: ({ sessionId, inputPlaceholder }: { sessionId: string; inputPlaceholder: string }) => (
    <div data-testid="chat-interface" data-session-id={sessionId}>
      <span data-testid="placeholder">{inputPlaceholder}</span>
    </div>
  ),
}));

const listSessions = vi.fn();
const createSession = vi.fn();
vi.mock("../../api/chat", async () => {
  const actual: Record<string, unknown> = await vi.importActual("../../api/chat");
  return {
    ...actual,
    listSessions: (...args: unknown[]) => listSessions(...args),
    createSession: (...args: unknown[]) => createSession(...args),
  };
});

import { SecretaryPage } from "../SecretaryPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <SecretaryPage user={{ id: "u1", display_name: "Alex" }} />
    </MemoryRouter>,
  );
}

describe("SecretaryPage mount session selection", () => {
  beforeEach(() => {
    listSessions.mockReset();
    createSession.mockReset();
  });

  it("lands on the head of listSessions when the list is non-empty", async () => {
    listSessions.mockResolvedValue({
      items: [
        {
          id: "most-recent",
          department: "secretary",
          title: "today",
          is_pinned: false,
          is_archived: false,
          created_at: "2026-05-04T00:00:00Z",
          model_id: null,
        },
        {
          id: "older",
          department: "secretary",
          title: "yesterday",
          is_pinned: false,
          is_archived: false,
          created_at: "2026-05-03T00:00:00Z",
          model_id: null,
        },
      ],
    });
    renderPage();
    const ci = await screen.findByTestId("chat-interface");
    await waitFor(() => expect(ci.getAttribute("data-session-id")).toBe("most-recent"));
    expect(createSession).not.toHaveBeenCalled();
  });

  it("creates a fresh session and lands on it when listSessions is empty", async () => {
    listSessions.mockResolvedValue({ items: [] });
    createSession.mockResolvedValue({
      id: "fresh",
      department: "secretary",
      title: "New chat",
      is_pinned: false,
      is_archived: false,
      created_at: "2026-05-04T00:00:00Z",
      model_id: null,
    });
    renderPage();
    const ci = await screen.findByTestId("chat-interface");
    await waitFor(() => expect(ci.getAttribute("data-session-id")).toBe("fresh"));
    expect(createSession).toHaveBeenCalledWith({ department: "secretary", title: "New chat" });
  });

  it("uses the spec-mandated input placeholder", async () => {
    listSessions.mockResolvedValue({
      items: [
        {
          id: "s1",
          department: "secretary",
          title: "t",
          is_pinned: false,
          is_archived: false,
          created_at: "2026-05-04T00:00:00Z",
          model_id: null,
        },
      ],
    });
    renderPage();
    expect(await screen.findByTestId("placeholder")).toHaveTextContent(/Ask LIA anything/);
  });
});
