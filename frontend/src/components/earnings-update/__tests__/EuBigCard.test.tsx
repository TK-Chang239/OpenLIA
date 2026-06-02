import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { CardHighlights } from "../../../api/earnings-update";
import { EuBigCard } from "../feed/EuBigCard";

const highlights: CardHighlights = {
  subtitle: "Beat on Services, in-line on iPhone",
  rating: "Buy",
  metrics: [
    { label: "Revenue", value: "$94.2B", change: "+5.4%", tone: "positive" },
    { label: "EPS", value: "$1.78", change: "+3.5%", tone: "positive" },
    { label: "Services", value: "$26.8B", change: "+15.2%", tone: "positive" },
    { label: "GM", value: "46.2%", change: null, tone: "neutral" },
  ],
};

describe("EuBigCard", () => {
  it("renders rating pill, subtitle from highlights, and metric chips (capped at 4)", () => {
    render(
      <EuBigCard
        ticker="AAPL"
        title="Apple Inc. — Earnings Update"
        status="complete"
        reportId="r1"
        highlights={{
          ...highlights,
          metrics: [...highlights.metrics, { label: "X", value: "1", change: null, tone: null }],
        }}
        onOpen={() => {}}
      />,
    );
    expect(screen.getByTestId("eu-rating-pill").textContent).toContain("Buy");
    expect(screen.getByText("Beat on Services, in-line on iPhone")).toBeTruthy();
    expect(screen.getAllByTestId("eu-metric-chip")).toHaveLength(4);
    expect(screen.getByText("$94.2B")).toBeTruthy();
  });

  it("renders without highlights (degrades to title only)", () => {
    render(
      <EuBigCard
        ticker="AAPL"
        title="Apple Inc. — Earnings Update"
        status="complete"
        reportId="r1"
        onOpen={() => {}}
      />,
    );
    expect(screen.getByText("Apple Inc. — Earnings Update")).toBeTruthy();
    expect(screen.queryByTestId("eu-metric-chip")).toBeNull();
    expect(screen.queryByTestId("eu-rating-pill")).toBeNull();
  });

  it("renders a delete control that calls onRemove on a completed card", () => {
    const onRemove = vi.fn();
    render(
      <EuBigCard
        ticker="AAPL"
        title="Apple Inc. — Earnings Update"
        status="complete"
        reportId="r1"
        onRemove={onRemove}
        onOpen={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /remove report/i }));
    expect(onRemove).toHaveBeenCalledWith("r1");
  });

  it("renders no delete control when streaming or when onRemove is absent", () => {
    const { rerender } = render(
      <EuBigCard
        ticker="AAPL"
        title="t"
        status="streaming"
        reportId="r1"
        onRemove={() => {}}
        onOpen={() => {}}
      />,
    );
    expect(screen.queryByRole("button", { name: /remove report/i })).toBeNull();
    rerender(
      <EuBigCard
        ticker="AAPL"
        title="t"
        status="complete"
        reportId="r1"
        onOpen={() => {}}
      />,
    );
    expect(screen.queryByRole("button", { name: /remove report/i })).toBeNull();
  });
});
