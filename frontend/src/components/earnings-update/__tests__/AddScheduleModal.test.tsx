import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AddScheduleModal } from "../AddScheduleModal";

describe("AddScheduleModal", () => {
  it("submits valid schedule", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<AddScheduleModal open onClose={() => {}} onSave={onSave} />);
    fireEvent.change(screen.getByLabelText("time"), {
      target: { value: "06:00" },
    });
    fireEvent.change(screen.getByLabelText("timezone"), {
      target: { value: "America/New_York" },
    });
    fireEvent.click(screen.getByLabelText("mon"));
    fireEvent.change(screen.getByLabelText("label"), {
      target: { value: "Pre-Market Scan" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave).toHaveBeenCalledWith({
      time: "06:00",
      timezone: "America/New_York",
      days_of_week: ["mon"],
      label: "Pre-Market Scan",
    });
  });

  it("requires at least one day selected", () => {
    const onSave = vi.fn();
    render(<AddScheduleModal open onClose={() => {}} onSave={onSave} />);
    fireEvent.change(screen.getByLabelText("time"), {
      target: { value: "06:00" },
    });
    fireEvent.change(screen.getByLabelText("timezone"), {
      target: { value: "America/New_York" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave).not.toHaveBeenCalled();
  });
});
