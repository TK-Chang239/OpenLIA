import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { UserBubble } from "../UserBubble";
import { AssistantMessage } from "../AssistantMessage";
import { ThinkingIndicator } from "../ThinkingIndicator";
import { ToolCallChip } from "../ToolCallChip";
import { ErrorMessage } from "../ErrorMessage";

describe("UserBubble", () => {
  it("renders content with role=article", () => {
    render(<UserBubble content="What moved the market?" />);
    expect(screen.getByRole("article")).toHaveTextContent("What moved the market?");
  });
});

describe("AssistantMessage", () => {
  it("renders content and shows LIA badge", () => {
    render(<AssistantMessage content="Top movers" streaming={false} />);
    expect(screen.getByText("Top movers")).toBeInTheDocument();
    expect(screen.getByLabelText("LIA")).toBeInTheDocument();
  });

  it("shows cursor when streaming=true", () => {
    render(<AssistantMessage content="partial" streaming={true} />);
    expect(screen.getByTestId("streaming-cursor")).toBeInTheDocument();
  });

  it("hides cursor when streaming=false", () => {
    render(<AssistantMessage content="done" streaming={false} />);
    expect(screen.queryByTestId("streaming-cursor")).toBeNull();
  });
});

describe("ThinkingIndicator", () => {
  it("announces LIA is thinking via aria-live role=status", () => {
    render(<ThinkingIndicator />);
    expect(screen.getByRole("status")).toHaveTextContent(/lia is thinking/i);
  });
});

describe("ToolCallChip", () => {
  it("renders running state with ellipsis", () => {
    render(<ToolCallChip toolName="get_quote" argsPreview="AAPL" status="running" />);
    expect(screen.getByText(/get_quote.*AAPL/i)).toBeInTheDocument();
  });

  it("renders done state with summary", () => {
    render(
      <ToolCallChip toolName="get_quote" argsPreview="AAPL" status="done" summary="Got AAPL" />,
    );
    expect(screen.getByText("Got AAPL")).toBeInTheDocument();
  });

  it("renders failed state", () => {
    render(
      <ToolCallChip toolName="get_quote" argsPreview="AAPL" status="failed" summary="Failed" />,
    );
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });
});

describe("ErrorMessage", () => {
  it("renders error and Try again button", () => {
    const retry = vi.fn();
    render(<ErrorMessage message="LLM unavailable" onRetry={retry} />);
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(retry).toHaveBeenCalled();
  });
});
