import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SourceChip } from "../SourceChip";

describe("SourceChip", () => {
  it("renders a non-interactive span when onClick is omitted", () => {
    render(<SourceChip label="report.pdf" kind="pdf" />);
    const el = screen.getByLabelText("report.pdf");
    expect(el.tagName.toLowerCase()).toBe("span");
  });

  it("renders an interactive button when onClick is provided", () => {
    const onClick = vi.fn();
    render(<SourceChip label="report.pdf" kind="pdf" onClick={onClick} />);
    const btn = screen.getByRole("button", { name: "report.pdf" });
    fireEvent.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("uses the supplied title for the accessible name", () => {
    render(
      <SourceChip
        label="r.pdf"
        kind="pdf"
        title="Report by Equity Research"
        onClick={() => {}}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Report by Equity Research" }),
    ).toBeInTheDocument();
  });
});
