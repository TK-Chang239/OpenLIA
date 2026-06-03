import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../../api/morning-briefing";
import * as settingsApi from "../../../api/settings";
import { MbRunNowModal } from "../MbRunNowModal";
import { RUN_NOW_LS_KEY } from "../mbRunNowDraft";

describe("MbRunNowModal", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
    vi.spyOn(api, "listMbTemplates").mockResolvedValue({ templates: [] });
    vi.spyOn(api, "listMbInstructions").mockResolvedValue([]);
    vi.spyOn(api, "getMbDataSources").mockResolvedValue({ sources: [] });
    vi.spyOn(settingsApi, "getEnabledModels").mockResolvedValue([]);
  });

  it("renders the full config controls and no schedule dropdown", async () => {
    render(<MbRunNowModal open onClose={vi.fn()} onStarted={vi.fn()} />);
    expect(await screen.findByTestId("mb-template-select")).toBeInTheDocument();
    expect(screen.getByTestId("mb-instructions-select")).toBeInTheDocument();
    expect(screen.getByTestId("mb-language-select")).toBeInTheDocument();
    expect(screen.queryByTestId("mb-run-now-schedule")).not.toBeInTheDocument();
  });

  it("starts an ad-hoc run, persists the draft, and reports the report id", async () => {
    const startSpy = vi
      .spyOn(api, "startMbRun")
      .mockResolvedValue({ report_id: "rNew" });
    const onStarted = vi.fn();
    render(<MbRunNowModal open onClose={vi.fn()} onStarted={onStarted} />);
    fireEvent.click(await screen.findByTestId("mb-run-now-start"));

    await waitFor(() => expect(onStarted).toHaveBeenCalledWith("rNew"));
    const payload = startSpy.mock.calls[0][0];
    expect(payload.schedule_id).toBeUndefined();
    expect(payload.template_id).toBe("mb_default");
    expect(payload.enabled_connectors).toEqual({
      provider_ids: [],
      web_search: false,
    });
    expect(window.localStorage.getItem(RUN_NOW_LS_KEY)).not.toBeNull();
  });

  it("disables Generate when freeform template has no instructions", async () => {
    window.localStorage.setItem(
      RUN_NOW_LS_KEY,
      JSON.stringify({ template_id: "freeform", instructions_id: null }),
    );
    render(<MbRunNowModal open onClose={vi.fn()} onStarted={vi.fn()} />);
    expect(await screen.findByTestId("mb-run-now-start")).toBeDisabled();
  });
});
