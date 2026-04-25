import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ChatInput } from "../ChatInput";

describe("ChatInput", () => {
  it("renders textarea with placeholder", () => {
    render(<ChatInput onSend={vi.fn()} isStreaming={false} placeholder="Ask LIA..." />);
    expect(screen.getByPlaceholderText("Ask LIA...")).toBeInTheDocument();
  });

  it("send button disabled when empty", () => {
    render(<ChatInput onSend={vi.fn()} isStreaming={false} placeholder="" />);
    expect(screen.getByLabelText("Send")).toBeDisabled();
  });

  it("send button enabled when text entered", () => {
    render(<ChatInput onSend={vi.fn()} isStreaming={false} placeholder="" />);
    fireEvent.change(screen.getByLabelText("Chat message"), { target: { value: "hello" } });
    expect(screen.getByLabelText("Send")).not.toBeDisabled();
  });

  it("calls onSend with trimmed text and clears input", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} isStreaming={false} placeholder="" />);
    fireEvent.change(screen.getByLabelText("Chat message"), { target: { value: "  hello  " } });
    fireEvent.click(screen.getByLabelText("Send"));
    expect(onSend).toHaveBeenCalledWith("hello");
    expect((screen.getByLabelText("Chat message") as HTMLTextAreaElement).value).toBe("");
  });

  it("Enter key submits message", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} isStreaming={false} placeholder="" />);
    const textarea = screen.getByLabelText("Chat message");
    fireEvent.change(textarea, { target: { value: "hi" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });
    expect(onSend).toHaveBeenCalledWith("hi");
  });

  it("Shift+Enter does not submit", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} isStreaming={false} placeholder="" />);
    const textarea = screen.getByLabelText("Chat message");
    fireEvent.change(textarea, { target: { value: "hi" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("shows stop button when streaming", () => {
    render(<ChatInput onSend={vi.fn()} onStop={vi.fn()} isStreaming={true} placeholder="" />);
    expect(screen.getByLabelText("Stop generating")).toBeInTheDocument();
    expect(screen.queryByLabelText("Send")).toBeNull();
  });

  it("calls onStop when stop button clicked", () => {
    const onStop = vi.fn();
    render(<ChatInput onSend={vi.fn()} onStop={onStop} isStreaming={true} placeholder="" />);
    fireEvent.click(screen.getByLabelText("Stop generating"));
    expect(onStop).toHaveBeenCalled();
  });

  it("renders the helper microcopy below the input row", () => {
    render(<ChatInput onSend={vi.fn()} isStreaming={false} placeholder="" />);
    expect(
      screen.getByText("Enter to send · Shift+Enter for new line"),
    ).toBeInTheDocument();
  });

  it("textarea has aria-describedby pointing at the helper element", () => {
    render(<ChatInput onSend={vi.fn()} isStreaming={false} placeholder="" />);
    const ta = screen.getByLabelText("Chat message");
    const id = ta.getAttribute("aria-describedby");
    expect(id).toBeTruthy();
    expect(document.getElementById(id!)?.textContent).toBe(
      "Enter to send · Shift+Enter for new line",
    );
  });
});
