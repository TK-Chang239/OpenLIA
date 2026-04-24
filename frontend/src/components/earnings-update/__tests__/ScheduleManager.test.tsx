import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ScheduleManager } from "../ScheduleManager";

describe("ScheduleManager", () => {
  it("empty state when no schedules", () => {
    render(
      <ScheduleManager
        schedules={[]}
        onCreate={vi.fn()}
        onUpdate={vi.fn()}
        onRemove={vi.fn()}
      />,
    );
    expect(screen.getByText(/No scan schedules/)).toBeInTheDocument();
  });

  it("lists schedules", () => {
    render(
      <ScheduleManager
        schedules={[
          {
            id: "s1",
            time: "06:00",
            timezone: "America/New_York",
            days_of_week: ["mon", "tue"],
            label: "Pre",
            is_enabled: true,
          },
        ]}
        onCreate={vi.fn()}
        onUpdate={vi.fn()}
        onRemove={vi.fn()}
      />,
    );
    expect(screen.getByText(/06:00/)).toBeInTheDocument();
    expect(screen.getByText(/Pre/)).toBeInTheDocument();
  });

  it("remove fires onRemove with id", () => {
    const onRemove = vi.fn();
    render(
      <ScheduleManager
        schedules={[
          {
            id: "s1",
            time: "06:00",
            timezone: "UTC",
            days_of_week: ["mon"],
            label: "x",
            is_enabled: true,
          },
        ]}
        onCreate={vi.fn()}
        onUpdate={vi.fn()}
        onRemove={onRemove}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /remove/i }));
    expect(onRemove).toHaveBeenCalledWith("s1");
  });
});
