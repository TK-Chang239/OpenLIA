import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../../../i18n";
import { EuHero } from "../EuHero";

describe("EuHero", () => {
  it("renders three real stat tiles with provided values", () => {
    render(
      <EuHero reportsThisWeek={5} trackedTickers={12} upcomingThisWeek={3} watchlistEmpty={false} />,
    );
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    // No fabricated labels remain.
    expect(screen.queryByText(/beats/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/surprise/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/latency/i)).not.toBeInTheDocument();
  });

  it("renders an em-dash when a count is null", () => {
    render(
      <EuHero reportsThisWeek={null} trackedTickers={0} upcomingThisWeek={0} watchlistEmpty />,
    );
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});
