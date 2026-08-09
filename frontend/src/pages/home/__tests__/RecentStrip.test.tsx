import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RecentStrip } from "../RecentStrip";
import * as chatApi from "../../../api/chat";
import type { ChatSession } from "../../../api/chat";

vi.mock("../../../api/chat", () => ({ listSessions: vi.fn() }));

const mocked = chatApi as unknown as {
  listSessions: ReturnType<typeof vi.fn>;
};

function session(overrides: Partial<ChatSession> = {}): ChatSession {
  return {
    id: "s1",
    department: "equity_research",
    title: "NVDA deep dive",
    is_pinned: false,
    is_archived: false,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("RecentStrip", () => {
  it("renders the five most recent sessions as deep links", async () => {
    mocked.listSessions.mockResolvedValue({
      items: [
        session({ id: "a", title: "Oldest", created_at: "2026-08-01T00:00:00Z" }),
        session({
          id: "b",
          title: "Newest",
          department: "morning_briefing",
          created_at: "2026-08-09T00:00:00Z",
        }),
      ],
    });
    render(
      <MemoryRouter>
        <RecentStrip />
      </MemoryRouter>,
    );
    const first = await screen.findByRole("link", { name: /Newest/ });
    // Most-recent first; equity_research -> /equity-research, mb -> /morning-briefing.
    expect(first).toHaveAttribute("href", "/morning-briefing");
    const links = screen.getAllByRole("link");
    expect(links[0]).toHaveTextContent("Newest");
    expect(links[1]).toHaveTextContent("Oldest");
  });

  it("renders nothing when there are no sessions", async () => {
    mocked.listSessions.mockResolvedValue({ items: [] });
    const { container } = render(
      <MemoryRouter>
        <RecentStrip />
      </MemoryRouter>,
    );
    await waitFor(() => expect(mocked.listSessions).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the fetch fails", async () => {
    mocked.listSessions.mockRejectedValue(new Error("boom"));
    const { container } = render(
      <MemoryRouter>
        <RecentStrip />
      </MemoryRouter>,
    );
    await waitFor(() => expect(mocked.listSessions).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
