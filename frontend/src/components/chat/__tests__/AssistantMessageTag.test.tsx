import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AssistantMessageTag } from "../AssistantMessageTag";

describe("AssistantMessageTag", () => {
  it("renders department · tokens · latency when all are provided", () => {
    render(
      <AssistantMessageTag
        departmentId="equity_research"
        tokens={1284}
        latencyMs={2123}
      />,
    );
    expect(
      screen.getByText("Equity Research · 1.3k tokens · 2.1s"),
    ).toBeInTheDocument();
  });

  it("formats sub-second latency in milliseconds", () => {
    render(<AssistantMessageTag departmentId="secretary" latencyMs={420} />);
    expect(screen.getByText("Secretary · 420ms")).toBeInTheDocument();
  });

  it("returns null when there is nothing to show", () => {
    const { container } = render(<AssistantMessageTag />);
    expect(container.firstChild).toBeNull();
  });

  it("drops missing pieces gracefully", () => {
    render(<AssistantMessageTag departmentId="secretary" tokens={250} />);
    expect(screen.getByText("Secretary · 250 tokens")).toBeInTheDocument();
  });
});
