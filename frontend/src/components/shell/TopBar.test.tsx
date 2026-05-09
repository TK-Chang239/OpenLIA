import { useEffect } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi } from "vitest";
import { TopBar } from "./TopBar";
import {
  ChatHeaderProvider,
  useChatHeaderRegistry,
  type ChatHeaderValue,
} from "../../layouts/ChatHeaderContext";

function HeaderRegistrar({ value }: { value: ChatHeaderValue }): null {
  const { register, clear } = useChatHeaderRegistry();
  useEffect(() => {
    register(value);
    return () => clear();
  }, [register, clear, value]);
  return null;
}

describe("TopBar", () => {
  it("renders breadcrumb segments with last as strong", () => {
    render(
      <MemoryRouter>
        <TopBar crumbs={["Home", "Morning Briefing"]} stamps={["TUE · 08:14 UTC"]} live />
      </MemoryRouter>,
    );
    expect(screen.getByText("Home")).toBeInTheDocument();
    const last = screen.getByText("Morning Briefing");
    expect(last.tagName).toBe("STRONG");
    expect(screen.getByText(/LIVE_FEED_ACTIVE/)).toBeInTheDocument();
  });

  it("omits the live pill when live is false", () => {
    render(
      <MemoryRouter>
        <TopBar crumbs={["Home"]} stamps={[]} live={false} />
      </MemoryRouter>,
    );
    expect(screen.queryByText(/LIVE_FEED_ACTIVE/)).toBeNull();
  });

  it("appends the chat title as a dropdown crumb and renders a New Chat button", () => {
    const onCreate = vi.fn();
    const onSelect = vi.fn();
    render(
      <MemoryRouter>
        <ChatHeaderProvider>
          <HeaderRegistrar
            value={{
              departmentId: "secretary",
              activeSessionId: "s1",
              chatTitle: "Today's market check",
              onSelect,
              onCreate,
            }}
          />
          <TopBar crumbs={["Home", "Secretary"]} stamps={[]} live={false} />
        </ChatHeaderProvider>
      </MemoryRouter>,
    );
    // Last department crumb stays as <strong>.
    const dept = screen.getByText("Secretary");
    expect(dept.tagName).toBe("STRONG");
    // The chat title is appended as a clickable trigger.
    const trigger = screen.getByRole("button", { name: /today's market check/i });
    expect(trigger).toBeInTheDocument();
    // "New Chat" labeled button is present.
    const newChat = screen.getByRole("button", { name: /new chat/i });
    expect(newChat).toBeInTheDocument();
    fireEvent.click(newChat);
    expect(onCreate).toHaveBeenCalledTimes(1);
  });

  it("omits the chat-title trigger when chatTitle is null (e.g. welcome state)", () => {
    render(
      <MemoryRouter>
        <ChatHeaderProvider>
          <HeaderRegistrar
            value={{
              departmentId: "equity_research",
              activeSessionId: null,
              chatTitle: null,
              onSelect: vi.fn(),
              onCreate: vi.fn(),
            }}
          />
          <TopBar crumbs={["Home", "Equity Research"]} stamps={[]} live={false} />
        </ChatHeaderProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText("Equity Research").tagName).toBe("STRONG");
    expect(
      screen.queryByRole("button", { name: /equity research/i }),
    ).toBeNull();
  });
});
