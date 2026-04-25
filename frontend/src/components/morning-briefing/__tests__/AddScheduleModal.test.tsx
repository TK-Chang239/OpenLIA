import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AddScheduleModal } from "../AddScheduleModal";

describe("AddScheduleModal", () => {
  it("populates fields from initial and submits payload", () => {
    const onSubmit = vi.fn();
    render(
      <AddScheduleModal
        open={true}
        onClose={() => {}}
        onSubmit={onSubmit}
        initial={{
          time: "08:30",
          timezone: "Asia/Tokyo",
          days_of_week: ["wed"],
          label: "Custom",
        }}
      />,
    );
    expect(
      (screen.getByTestId("add-schedule-time") as HTMLInputElement).value,
    ).toBe("08:30");
    expect(
      (screen.getByTestId("add-schedule-tz") as HTMLSelectElement).value,
    ).toBe("Asia/Tokyo");
    expect(
      (screen.getByTestId("add-schedule-label") as HTMLInputElement).value,
    ).toBe("Custom");
    expect(screen.getByTestId("add-schedule-day-wed")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    fireEvent.click(screen.getByTestId("add-schedule-submit"));
    expect(onSubmit).toHaveBeenCalledWith({
      time: "08:30",
      timezone: "Asia/Tokyo",
      days_of_week: ["wed"],
      label: "Custom",
    });
  });

  it("toggles a day on click", () => {
    const onSubmit = vi.fn();
    render(
      <AddScheduleModal
        open={true}
        onClose={() => {}}
        onSubmit={onSubmit}
        initial={{
          time: "07:00",
          timezone: "UTC",
          days_of_week: ["mon"],
          label: "",
        }}
      />,
    );
    fireEvent.click(screen.getByTestId("add-schedule-day-tue"));
    fireEvent.click(screen.getByTestId("add-schedule-submit"));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ days_of_week: ["mon", "tue"] }),
    );
  });
});
