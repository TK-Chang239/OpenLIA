import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { MbSchedule } from "../../../api/morning-briefing";
import { ScheduleRow } from "../ScheduleRow";

const schedule: MbSchedule = {
  id: "s-1",
  time: "07:00",
  timezone: "America/New_York",
  days_of_week: ["mon", "tue"],
  label: "Pre-Market",
  is_enabled: true,
};

describe("ScheduleRow", () => {
  it("renders schedule details", () => {
    render(
      <ScheduleRow
        schedule={schedule}
        onEdit={() => {}}
        onDelete={() => {}}
      />,
    );
    expect(screen.getByText("07:00")).toBeInTheDocument();
    expect(screen.getByText(/America\/New_York/)).toBeInTheDocument();
    expect(screen.getByText(/Pre-Market/)).toBeInTheDocument();
  });

  it("fires onEdit + onDelete", () => {
    const onEdit = vi.fn();
    const onDelete = vi.fn();
    render(
      <ScheduleRow
        schedule={schedule}
        onEdit={onEdit}
        onDelete={onDelete}
      />,
    );
    fireEvent.click(screen.getByTestId("schedule-row-edit-s-1"));
    expect(onEdit).toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("schedule-row-delete-s-1"));
    expect(onDelete).toHaveBeenCalled();
  });
});
