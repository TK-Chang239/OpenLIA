import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { MbCardHighlights } from "../../../api/morning-briefing";
import { MbBigCard } from "../feed/MbBigCard";

const highlights: MbCardHighlights = {
  subtitle: "Rate-cut hopes lift equities; oil slips",
  rating: "Risk-On",
  metrics: [
    { label: "S&P 500", value: "5,420", change: "+0.8%", tone: "positive" },
    { label: "10Y", value: "4.12%", change: "-3bp", tone: "positive" },
    { label: "VIX", value: "13.4", change: "-2.1%", tone: "positive" },
    { label: "WTI", value: "$78", change: null, tone: "neutral" },
  ],
};

describe("MbBigCard", () => {
  it("renders subject, subtitle from highlights, rating, and capped metric chips", () => {
    render(
      <MbBigCard
        title="Markets open higher on rate-cut hopes"
        status="complete"
        reportId="r1"
        highlights={{
          ...highlights,
          metrics: [
            ...highlights.metrics,
            { label: "X", value: "1", change: null, tone: null },
          ],
        }}
        onOpen={() => {}}
      />,
    );
    expect(
      screen.getByText("Markets open higher on rate-cut hopes"),
    ).toBeTruthy();
    expect(screen.getByTestId("mb-rating-pill").textContent).toContain(
      "Risk-On",
    );
    expect(
      screen.getByText("Rate-cut hopes lift equities; oil slips"),
    ).toBeTruthy();
    expect(screen.getAllByTestId("mb-metric-chip")).toHaveLength(4);
  });

  it("degrades to title only without highlights", () => {
    render(
      <MbBigCard
        title="Morning Briefing"
        status="complete"
        reportId="r1"
        onOpen={() => {}}
      />,
    );
    expect(screen.getByText("Morning Briefing")).toBeTruthy();
    expect(screen.queryByTestId("mb-metric-chip")).toBeNull();
    expect(screen.queryByTestId("mb-rating-pill")).toBeNull();
  });

  it("renders a delete control that calls onRemove on a completed card", () => {
    const onRemove = vi.fn();
    render(
      <MbBigCard
        title="Morning Briefing"
        status="complete"
        reportId="r1"
        onRemove={onRemove}
        onOpen={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /remove briefing/i }));
    expect(onRemove).toHaveBeenCalledWith("r1");
  });

  it("renders no delete control while streaming", () => {
    render(
      <MbBigCard
        title="t"
        status="streaming"
        reportId="r1"
        onRemove={() => {}}
        onOpen={() => {}}
      />,
    );
    expect(
      screen.queryByRole("button", { name: /remove briefing/i }),
    ).toBeNull();
  });
});
