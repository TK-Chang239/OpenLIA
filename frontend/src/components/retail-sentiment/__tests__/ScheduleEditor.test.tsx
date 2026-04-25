import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ScheduleEditor } from "../ScheduleEditor";

describe("ScheduleEditor", () => {
  it("does not render when closed", () => {
    render(
      <ScheduleEditor
        open={false}
        schedule={null}
        onClose={() => {}}
        onSave={async () => ({
          id: "x",
          time: "08:00",
          timezone: "UTC",
          days_of_week: [],
          label: "",
          is_enabled: true,
        })}
      />,
    );
    expect(screen.queryByTestId("schedule-editor")).toBeNull();
  });

  it("calls onSave with form values", async () => {
    const onSave = vi.fn().mockResolvedValue({
      id: "x",
      time: "09:30",
      timezone: "UTC",
      days_of_week: ["mon"],
      label: "test",
      is_enabled: true,
    });
    render(
      <ScheduleEditor
        open
        schedule={null}
        onClose={() => {}}
        onSave={onSave}
      />,
    );
    fireEvent.click(screen.getByText("Save"));
    await waitFor(() => {
      expect(onSave).toHaveBeenCalled();
    });
  });
});
