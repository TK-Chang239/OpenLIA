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

  it("renders a clickable last-crumb trigger and a New Chat button when chat header is registered", () => {
    const onCreate = vi.fn();
    const onSelect = vi.fn();
    render(
      <MemoryRouter>
        <ChatHeaderProvider>
          <HeaderRegistrar
            value={{
              departmentId: "secretary",
              activeSessionId: "s1",
              onSelect,
              onCreate,
            }}
          />
          <TopBar crumbs={["Home", "Secretary"]} stamps={[]} live={false} />
        </ChatHeaderProvider>
      </MemoryRouter>,
    );
    // Last crumb becomes a button "Secretary ▾"
    const trigger = screen.getByRole("button", { name: /secretary/i });
    expect(trigger).toBeInTheDocument();
    expect(trigger.tagName).toBe("BUTTON");
    // "New Chat" labeled button is present.
    const newChat = screen.getByRole("button", { name: /new chat/i });
    expect(newChat).toBeInTheDocument();
    fireEvent.click(newChat);
    expect(onCreate).toHaveBeenCalledTimes(1);
  });
});
