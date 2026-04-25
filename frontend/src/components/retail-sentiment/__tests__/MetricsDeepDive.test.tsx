import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MetricsDeepDive } from "../MetricsDeepDive";

describe("MetricsDeepDive", () => {
  it("does not render when closed", () => {
    render(<MetricsDeepDive open={false} onClose={() => {}} />);
    expect(screen.queryByTestId("metrics-deep-dive")).toBeNull();
  });

  it("renders all 12 metric sections when open", () => {
    render(<MetricsDeepDive open onClose={() => {}} />);
    const drawer = screen.getByTestId("metrics-deep-dive");
    const sections = drawer.querySelectorAll("section");
    expect(sections.length).toBe(12);
  });

  it("invokes onClose when close button clicked", () => {
    const onClose = vi.fn();
    render(<MetricsDeepDive open onClose={onClose} />);
    fireEvent.click(screen.getByLabelText("Close metrics deep dive"));
    expect(onClose).toHaveBeenCalled();
  });
});
