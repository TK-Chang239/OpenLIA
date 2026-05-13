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

  describe("markdown rendering", () => {
    it("renders ### as an uppercase mono heading", () => {
      render(<AssistantMessage content="### What's moving" streaming={false} />);
      const heading = screen.getByRole("heading", { level: 3, name: /what's moving/i });
      expect(heading.className).toMatch(/uppercase/);
      expect(heading.className).toMatch(/font-mono/);
    });

    it("renders ## and # at the same h3 level (defensive against disobedient models)", () => {
      render(<AssistantMessage content={"## Big one\n# Bigger"} streaming={false} />);
      expect(screen.getByRole("heading", { level: 3, name: /big one/i })).toBeInTheDocument();
      expect(screen.getByRole("heading", { level: 3, name: /bigger/i })).toBeInTheDocument();
    });

    it("renders bullet lists with list-disc styling", () => {
      render(<AssistantMessage content={"- one\n- two\n- three"} streaming={false} />);
      const list = screen.getByRole("list");
      expect(list.tagName).toBe("UL");
      expect(list.className).toMatch(/list-disc/);
      expect(screen.getAllByRole("listitem")).toHaveLength(3);
    });

    it("renders numbered lists as ordered with list-decimal", () => {
      render(<AssistantMessage content={"1. first\n2. second"} streaming={false} />);
      const list = screen.getByRole("list");
      expect(list.tagName).toBe("OL");
      expect(list.className).toMatch(/list-decimal/);
    });

    it("renders **bold** as a semibold strong element", () => {
      render(<AssistantMessage content="The answer is **42**." streaming={false} />);
      const strong = screen.getByText("42");
      expect(strong.tagName).toBe("STRONG");
      expect(strong.className).toMatch(/font-semibold/);
    });

    it("renders GFM tables with bordered cells and a mono header row", () => {
      render(
        <AssistantMessage
          content={"| Ticker | Price |\n| --- | --- |\n| AAPL | 230.15 |"}
          streaming={false}
        />,
      );
      const table = screen.getByRole("table");
      expect(table.className).toMatch(/font-mono/);
      const headerCell = screen.getByRole("columnheader", { name: /ticker/i });
      expect(headerCell.className).toMatch(/uppercase/);
      expect(screen.getByRole("cell", { name: /aapl/i })).toBeInTheDocument();
    });
  });
});

describe("ThinkingIndicator", () => {
  it("announces LIA is thinking via aria-live role=status", () => {
    render(<ThinkingIndicator />);
    expect(screen.getByRole("status")).toHaveTextContent(/lia is thinking/i);
  });
});

describe("ToolCallChip", () => {
  it("renders running state with the friendly mapped label", () => {
    render(<ToolCallChip toolName="get_quote" argsPreview="AAPL" status="running" />);
    // get_quote is mapped to "Market data — <ticker/args>".
    expect(screen.getByText(/market data — aapl/i)).toBeInTheDocument();
  });

  it("renders done state with the supplied summary verbatim", () => {
    render(
      <ToolCallChip toolName="get_quote" argsPreview="AAPL" status="done" summary="Got AAPL" />,
    );
    expect(screen.getByText("Got AAPL")).toBeInTheDocument();
  });

  it("renders failed state with a `<tool> failed` label", () => {
    render(
      <ToolCallChip toolName="get_quote" argsPreview="AAPL" status="failed" summary="Failed" />,
    );
    expect(screen.getByText(/get_quote failed/i)).toBeInTheDocument();
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
