import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Hero } from "../sections/Hero";
import { heroCopy, summaryStats } from "../../../lib/panic_thermometer/copy/summary";

describe("Hero", () => {
  it("renders headline, accent, and stats", () => {
    render(
      <Hero hero={heroCopy} stats={summaryStats} mode="count" onModeChange={() => {}} />,
    );
    expect(screen.getByText("Three of five indicators red.")).toBeInTheDocument();
    expect(
      screen.getByText(/Wage spiral and Fed hawkish pivot/),
    ).toBeInTheDocument();
    expect(screen.getByText("Composite")).toBeInTheDocument();
    expect(screen.getByText("SEVERE")).toBeInTheDocument();
    expect(screen.getByText("3.2 / 5.0")).toBeInTheDocument();
  });

  it("renders the 5-row scale list with current row marked", () => {
    render(
      <Hero hero={heroCopy} stats={summaryStats} mode="count" onModeChange={() => {}} />,
    );
    expect(screen.getByText("Calm")).toBeInTheDocument();
    expect(screen.getByText("Elevated")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getAllByText("Severe").length).toBeGreaterThan(0);
    expect(screen.getByText("Crisis")).toBeInTheDocument();
    expect(screen.getByText("▶ today")).toBeInTheDocument();
  });

  it("toggles mode via Count/Weighted buttons", () => {
    const onModeChange = vi.fn();
    render(
      <Hero hero={heroCopy} stats={summaryStats} mode="count" onModeChange={onModeChange} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Weighted" }));
    expect(onModeChange).toHaveBeenCalledWith("weighted");
  });
});
