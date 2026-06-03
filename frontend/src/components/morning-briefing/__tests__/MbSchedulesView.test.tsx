import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { MbSchedule } from "../../../api/morning-briefing";
import { MbSchedulesView } from "../MbSchedulesView";

function makeSchedule(over: Partial<MbSchedule> = {}): MbSchedule {
  return {
    id: "s1",
    time: "07:00",
    timezone: "America/New_York",
    days_of_week: ["mon", "tue", "wed", "thu", "fri"],
    label: "Pre-Market",
    is_enabled: true,
    template_id: "freeform",
    instructions_id: null,
    enabled_connectors: { provider_ids: [], web_search: false },
    provider_kind: null,
    model: null,
    language: "en",
    length: "normal",
    reasoning_effort: null,
    web_search: false,
    ...over,
  };
}

describe("MbSchedulesView", () => {
  it("renders an empty state with an add CTA when there are no schedules", () => {
    const onAdd = vi.fn();
    render(
      <MbSchedulesView
        schedules={[]}
        onBack={vi.fn()}
        onAdd={onAdd}
        onEdit={vi.fn()}
        onRemove={vi.fn().mockResolvedValue(undefined)}
      />,
    );
    expect(screen.getByTestId("mb-schedules-empty")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("mb-schedules-empty-add"));
    expect(onAdd).toHaveBeenCalledTimes(1);
  });

  it("renders a schedule row and routes Edit", () => {
    const onEdit = vi.fn();
    render(
      <MbSchedulesView
        schedules={[makeSchedule()]}
        onBack={vi.fn()}
        onAdd={vi.fn()}
        onEdit={onEdit}
        onRemove={vi.fn().mockResolvedValue(undefined)}
      />,
    );
    expect(screen.getByTestId("mb-schedule-row")).toBeInTheDocument();
    expect(screen.getByText("Pre-Market")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("mb-schedule-edit-s1"));
    expect(onEdit).toHaveBeenCalledTimes(1);
    // Edit must hand back the full schedule object, not just its id.
    expect(onEdit).toHaveBeenCalledWith(makeSchedule());
  });
});
