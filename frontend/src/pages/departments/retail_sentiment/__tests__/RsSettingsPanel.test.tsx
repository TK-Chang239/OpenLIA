import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as deptHealth from "../../../../api/dept-health";
import * as api from "../../../../api/retail-sentiment";
import RsSettingsPanel from "../RsSettingsPanel";

function stubAll(overrides: Partial<deptHealth.DepartmentHealth> = {}) {
  vi.spyOn(deptHealth, "fetchDeptHealth").mockResolvedValue([
    {
      department_id: "retail_sentiment",
      status: "active",
      reason: null,
      missing_categories: [],
      unresolved_needs: [],
      satisfied_categories: ["web_search"],
      optional_categories: ["financial", "news"],
      required_categories: ["web_search"],
      ...overrides,
    },
  ]);
  vi.spyOn(api, "getSchedule").mockResolvedValue({ schedule: null });
}

describe("RsSettingsPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the panel with data-testid", () => {
    stubAll();
    render(<RsSettingsPanel onClose={() => undefined} />);
    expect(screen.getByTestId("rs-settings-panel")).toBeInTheDocument();
  });

  it("shows rs-coverage section when dept-health resolves", async () => {
    stubAll();
    render(<RsSettingsPanel onClose={() => undefined} />);
    await waitFor(() => {
      expect(screen.getByTestId("rs-coverage")).toBeInTheDocument();
    });
  });

  it("shows web_search as active when satisfied", async () => {
    stubAll({ satisfied_categories: ["web_search"] });
    render(<RsSettingsPanel onClose={() => undefined} />);
    await waitFor(() => {
      const webSearchItem = screen.getByTestId("rs-coverage-web_search");
      expect(webSearchItem).toHaveTextContent("active");
    });
  });

  it("shows web_search as required when not satisfied", async () => {
    stubAll({ satisfied_categories: [] });
    render(<RsSettingsPanel onClose={() => undefined} />);
    await waitFor(() => {
      const webSearchItem = screen.getByTestId("rs-coverage-web_search");
      expect(webSearchItem).toHaveTextContent("required");
    });
  });

  it("shows financial as not configured when not satisfied", async () => {
    stubAll({ satisfied_categories: ["web_search"] });
    render(<RsSettingsPanel onClose={() => undefined} />);
    await waitFor(() => {
      const financialItem = screen.getByTestId("rs-coverage-financial");
      expect(financialItem).toHaveTextContent("not configured");
    });
  });

  it("shows financial as active when satisfied", async () => {
    stubAll({ satisfied_categories: ["web_search", "financial"] });
    render(<RsSettingsPanel onClose={() => undefined} />);
    await waitFor(() => {
      const financialItem = screen.getByTestId("rs-coverage-financial");
      expect(financialItem).toHaveTextContent("active");
    });
  });

  it("shows news as active when satisfied", async () => {
    stubAll({ satisfied_categories: ["web_search", "news"] });
    render(<RsSettingsPanel onClose={() => undefined} />);
    await waitFor(() => {
      const newsItem = screen.getByTestId("rs-coverage-news");
      expect(newsItem).toHaveTextContent("active");
    });
  });

  it("shows news as not configured when not satisfied", async () => {
    stubAll({ satisfied_categories: ["web_search"] });
    render(<RsSettingsPanel onClose={() => undefined} />);
    await waitFor(() => {
      const newsItem = screen.getByTestId("rs-coverage-news");
      expect(newsItem).toHaveTextContent("not configured");
    });
  });

  it("does not render coverage section when dept-health fails", async () => {
    vi.spyOn(deptHealth, "fetchDeptHealth").mockRejectedValue(new Error("network"));
    vi.spyOn(api, "getSchedule").mockResolvedValue({ schedule: null });
    render(<RsSettingsPanel onClose={() => undefined} />);
    // Give time for the failed fetch to settle
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByTestId("rs-coverage")).not.toBeInTheDocument();
  });
});
