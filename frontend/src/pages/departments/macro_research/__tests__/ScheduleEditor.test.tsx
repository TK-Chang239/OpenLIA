import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getSchedule: vi.fn(),
  putSchedule: vi.fn(),
  deleteSchedule: vi.fn(),
}));

vi.mock("../../../../api/macro_research", () => mocks);

import ScheduleEditor from "../ScheduleEditor";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getSchedule.mockResolvedValue({
    cron_expression: "0 0 * * 0",
    last_assessment_at: null,
  });
  mocks.putSchedule.mockResolvedValue({ cron_expression: "0 0 * * 0" });
  mocks.deleteSchedule.mockResolvedValue(null);
});

describe("ScheduleEditor", () => {
  it("prefills cron from existing schedule", async () => {
    render(<ScheduleEditor onClose={() => {}} />);
    await waitFor(() => {
      const input = screen.getByPlaceholderText("0 0 * * 0") as HTMLInputElement;
      expect(input.value).toBe("0 0 * * 0");
    });
  });

  it("weekly preset fills cron input", async () => {
    render(<ScheduleEditor onClose={() => {}} />);
    const weekly = await screen.findByRole("button", { name: /weekly/i });
    fireEvent.click(weekly);
    const input = screen.getByPlaceholderText("0 0 * * 0") as HTMLInputElement;
    expect(input.value).toBe("0 0 * * 0");
  });

  it("quarterly preset uses the quarterly cron", async () => {
    render(<ScheduleEditor onClose={() => {}} />);
    const q = await screen.findByRole("button", { name: /quarterly/i });
    fireEvent.click(q);
    const input = screen.getByPlaceholderText("0 0 * * 0") as HTMLInputElement;
    expect(input.value).toBe("0 0 1 */3 *");
  });

  it("save calls putSchedule and closes", async () => {
    const onClose = vi.fn();
    render(<ScheduleEditor onClose={onClose} />);
    await screen.findByPlaceholderText("0 0 * * 0");
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() =>
      expect(mocks.putSchedule).toHaveBeenCalledWith("0 0 * * 0"),
    );
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("cancel closes without saving", async () => {
    const onClose = vi.fn();
    render(<ScheduleEditor onClose={onClose} />);
    await screen.findByPlaceholderText("0 0 * * 0");
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalled();
    expect(mocks.putSchedule).not.toHaveBeenCalled();
  });
});
