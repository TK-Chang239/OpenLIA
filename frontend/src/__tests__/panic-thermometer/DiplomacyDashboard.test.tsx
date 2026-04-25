import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DiplomacyDashboard } from "../../components/panic-thermometer/DiplomacyDashboard";

describe("DiplomacyDashboard", () => {
  it("renders progress bar and Mark milestone button", () => {
    const onMark = vi.fn();
    render(
      <DiplomacyDashboard
        result={{
          panel_id: "diplomacy",
          status: "amber",
          label: "10 days remaining",
          resolved_values: { window_days: 30 },
          derived_scalars: {},
          extras: {
            days_elapsed: 20,
            days_remaining: 10,
            matched_progress_headlines: ["talks resumed"],
            matched_escalation_headlines: [],
          },
          warnings: [],
        }}
        onMarkMilestone={onMark}
      />,
    );
    expect(screen.getByTestId("diplomacy-progress")).toBeInTheDocument();
    expect(screen.getByText(/talks resumed/)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("diplomacy-mark-milestone"));
    expect(onMark).toHaveBeenCalled();
  });
});
