import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MbHero } from "../feed/MbHero";

describe("MbHero", () => {
  it("renders the three stat values", () => {
    render(
      <MbHero
        briefingsThisWeek={5}
        activeSchedules={2}
        nextRun="Tomorrow · 7:00 AM EST"
      />,
    );
    expect(screen.getByTestId("mb-hero")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Tomorrow · 7:00 AM EST")).toBeInTheDocument();
  });

  it("falls back to an em dash when there is no next run", () => {
    render(<MbHero briefingsThisWeek={0} activeSchedules={0} nextRun={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
    // Zero is a real state (no briefings yet) — guard against a future
    // `value || DASH` regression by asserting both counts render as "0".
    expect(screen.getAllByText("0")).toHaveLength(2);
  });
});
