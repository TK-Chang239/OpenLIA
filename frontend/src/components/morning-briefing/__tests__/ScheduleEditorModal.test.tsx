import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../../api/morning-briefing";
import * as settingsApi from "../../../api/settings";
import type { MbSchedule } from "../../../api/morning-briefing";
import { ScheduleEditorModal } from "../ScheduleEditorModal";

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

describe("ScheduleEditorModal", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listMbTemplates").mockResolvedValue({ templates: [] });
    vi.spyOn(api, "listMbInstructions").mockResolvedValue([]);
    vi.spyOn(api, "getMbDataSources").mockResolvedValue({ sources: [] });
    vi.spyOn(settingsApi, "getEnabledModels").mockResolvedValue([]);
  });

  it("renders both the binding controls and the scheduling fields", async () => {
    render(
      <ScheduleEditorModal
        schedule={makeSchedule()}
        onSave={vi.fn().mockResolvedValue(undefined)}
        onClose={vi.fn()}
      />,
    );
    // Scheduling fields
    expect(await screen.findByTestId("mb-schedule-time")).toBeInTheDocument();
    expect(screen.getByTestId("mb-schedule-timezone")).toBeInTheDocument();
    expect(screen.getByTestId("mb-schedule-day-mon")).toBeInTheDocument();
    expect(screen.getByTestId("mb-schedule-label")).toBeInTheDocument();
    expect(screen.getByTestId("mb-schedule-enabled")).toBeInTheDocument();
    // Binding controls (EU-style config)
    expect(screen.getByTestId("mb-template-select")).toBeInTheDocument();
    expect(screen.getByTestId("mb-instructions-select")).toBeInTheDocument();
    expect(screen.getByTestId("mb-language-select")).toBeInTheDocument();
    expect(screen.getByTestId("mb-schedule-save")).toBeInTheDocument();
  });

  it("seeds the time field from the edited schedule", async () => {
    render(
      <ScheduleEditorModal
        schedule={makeSchedule({ time: "09:30" })}
        onSave={vi.fn().mockResolvedValue(undefined)}
        onClose={vi.fn()}
      />,
    );
    const time = (await screen.findByTestId(
      "mb-schedule-time",
    )) as HTMLInputElement;
    expect(time.value).toBe("09:30");
  });

  it("disables save and shows the error when freeform template has no instructions", async () => {
    render(
      <ScheduleEditorModal
        schedule={makeSchedule({
          template_id: "freeform",
          instructions_id: null,
        })}
        onSave={vi.fn().mockResolvedValue(undefined)}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() =>
      expect(screen.getByTestId("mb-both-empty-error")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("mb-schedule-save")).toBeDisabled();
  });
});
