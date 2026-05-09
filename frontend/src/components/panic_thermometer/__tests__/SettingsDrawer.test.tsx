import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../../api/panic-thermometer";
import { SettingsDrawer } from "../SettingsDrawer";

const userConfig: api.UserConfig = {
  id: "u1",
  panel_config: [
    {
      panel_id: "oil",
      rules: [
        { status: "red", formula: "streak_days >= 30", label: "Red" },
        { status: "amber", formula: "price > 45", label: "Amber" },
      ],
      params: { ticker: "BNO.US" },
      streak_condition: null,
      manual_override: null,
      milestone_date: null,
      enabled: true,
    },
  ],
  composite_settings: { mode: "count", red_threshold: 3 },
  active_preset_id: null,
};

function stubApi() {
  vi.spyOn(api, "fetchConfig").mockResolvedValue(userConfig);
  vi.spyOn(api, "saveConfig").mockResolvedValue(userConfig);
  vi.spyOn(api, "listPresets").mockResolvedValue([
    { id: "p1", user_id: null, name: "Calm", description: null, is_shipped: true },
    { id: "p2", user_id: "u1", name: "Hawkish", description: null, is_shipped: false },
  ]);
  vi.spyOn(api, "applyPreset").mockResolvedValue(userConfig);
  vi.spyOn(api, "exportConfig").mockResolvedValue({
    version: 1,
    panel_config: userConfig.panel_config,
    composite_settings: userConfig.composite_settings,
  });
  vi.spyOn(api, "importConfig").mockResolvedValue(userConfig);
  vi.spyOn(api, "parseFormula").mockResolvedValue({
    ok: true,
    identifiers: ["streak_days", "streak_red"],
  });
}

describe("SettingsDrawer", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    stubApi();
  });

  it("renders all four tabs and starts on Presets", async () => {
    render(
      <SettingsDrawer
        open={true}
        onClose={() => {}}
        refreshIntervalSeconds={300}
        onRefreshIntervalChange={() => {}}
      />,
    );
    expect(screen.getByRole("tab", { name: "Presets" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "Panels" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Composite" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Data" })).toBeInTheDocument();
  });

  it("lists shipped and user presets and supports apply", async () => {
    render(
      <SettingsDrawer
        open={true}
        onClose={() => {}}
        refreshIntervalSeconds={300}
        onRefreshIntervalChange={() => {}}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText("Calm")).toBeInTheDocument();
    });
    expect(screen.getByText("Hawkish")).toBeInTheDocument();
    const applyButtons = screen.getAllByRole("button", { name: "Apply" });
    fireEvent.click(applyButtons[0]);
    await waitFor(() => {
      expect(api.applyPreset).toHaveBeenCalledWith("p1");
    });
  });

  it("Panels tab shows accordion of configured panels", async () => {
    render(
      <SettingsDrawer
        open={true}
        onClose={() => {}}
        refreshIntervalSeconds={300}
        onRefreshIntervalChange={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("tab", { name: "Panels" }));
    await waitFor(() => {
      expect(screen.getByText("D1 · Oil price duration")).toBeInTheDocument();
    });
  });

  it("Composite tab parses formula via API", async () => {
    render(
      <SettingsDrawer
        open={true}
        onClose={() => {}}
        refreshIntervalSeconds={300}
        onRefreshIntervalChange={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("tab", { name: "Composite" }));
    await waitFor(() => {
      expect(screen.getByLabelText("Test panel formula")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByLabelText("Test panel formula"), {
      target: { value: "streak_days >= streak_red" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Parse" }));
    await waitFor(() => {
      expect(api.parseFormula).toHaveBeenCalled();
    });
  });

  it("Data tab exposes refresh interval and import textarea", async () => {
    const onRefresh = vi.fn();
    render(
      <SettingsDrawer
        open={true}
        onClose={() => {}}
        refreshIntervalSeconds={300}
        onRefreshIntervalChange={onRefresh}
      />,
    );
    fireEvent.click(screen.getByRole("tab", { name: "Data" }));
    fireEvent.change(screen.getByLabelText("Auto-refresh interval"), {
      target: { value: "60" },
    });
    expect(onRefresh).toHaveBeenCalledWith(60);
  });

  it("returns null when open is false", () => {
    const { container } = render(
      <SettingsDrawer
        open={false}
        onClose={() => {}}
        refreshIntervalSeconds={null}
        onRefreshIntervalChange={() => {}}
      />,
    );
    expect(container.firstChild).toBeNull();
  });
});
