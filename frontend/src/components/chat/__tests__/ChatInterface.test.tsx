import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ChatInterface } from "../ChatInterface";
import * as chatApi from "../../../api/chat";

vi.mock("../useChatStream", () => ({
  useChatStream: () => ({
    state: {
      status: "idle",
      message: "",
      chunks: [],
      toolCalls: [],
      reportThumbnails: [],
      errorMessage: null,
    },
    send: vi.fn(),
    stop: vi.fn(),
    reset: vi.fn(),
  }),
}));

const SESSION_ID = "00000000-0000-4000-8000-000000000001";

describe("ChatInterface", () => {
  beforeEach(() => {
    vi.spyOn(chatApi, "listMessages").mockResolvedValue({ items: [] });
  });

  it("shows welcome overlay when there are no messages", async () => {
    render(
      <ChatInterface
        sessionId={SESSION_ID}
        greeting="Good evening"
        subtext="Ask LIA"
        chips={[]}
        inputPlaceholder="Ask"
      />,
    );
    await waitFor(() => screen.getByText("Good evening"));
  });

  it("hides welcome overlay after first send", async () => {
    render(
      <ChatInterface
        sessionId={SESSION_ID}
        greeting="Good evening"
        subtext="Ask LIA"
        chips={[]}
        inputPlaceholder="Ask"
      />,
    );
    await waitFor(() => screen.getByText("Good evening"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "hello" } });
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });
    await waitFor(() => expect(screen.queryByText("Good evening")).toBeNull());
  });

  it("renders persisted messages from the backend", async () => {
    vi.spyOn(chatApi, "listMessages").mockResolvedValue({
      items: [
        {
          id: "00000000-0000-4000-8000-000000000002",
          role: "user",
          content: "hi",
          tool_calls: null,
          model_ref: null,
          token_usage: null,
          created_at: "2026-04-01T00:00:00Z",
        },
        {
          id: "00000000-0000-4000-8000-000000000003",
          role: "assistant",
          content: "hello",
          tool_calls: null,
          model_ref: null,
          token_usage: null,
          created_at: "2026-04-01T00:00:00Z",
        },
      ],
    });
    render(
      <ChatInterface
        sessionId={SESSION_ID}
        greeting="x"
        subtext=""
        chips={[]}
        inputPlaceholder="Ask"
      />,
    );
    await waitFor(() => screen.getByText("hi"));
    expect(screen.getByText("hello")).toBeInTheDocument();
  });
});
