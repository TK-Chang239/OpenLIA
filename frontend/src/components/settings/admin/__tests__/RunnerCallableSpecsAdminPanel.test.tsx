import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { RunnerCallableSpecsAdminPanel } from "../RunnerCallableSpecsAdminPanel";
import * as runnerApi from "../../../../api/runner_specs";
import * as connectorsApi from "../../../../api/connectors";

vi.mock("../../../../api/runner_specs", async () => {
  const actual = await vi.importActual<typeof runnerApi>(
    "../../../../api/runner_specs",
  );
  return { ...actual, listRunnerSpecs: vi.fn() };
});

vi.mock("../../../../api/connectors", async () => {
  const actual = await vi.importActual<typeof connectorsApi>(
    "../../../../api/connectors",
  );
  return { ...actual, reResolveSpecs: vi.fn() };
});

const mocked = runnerApi as unknown as {
  listRunnerSpecs: ReturnType<typeof vi.fn>;
};
const mockedConnectors = connectorsApi as unknown as {
  reResolveSpecs: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("RunnerCallableSpecsAdminPanel", () => {
  it("groups rows by department_id", async () => {
    mocked.listRunnerSpecs.mockResolvedValue([
      {
        id: "rcs-1",
        department_id: "macro_research",
        need_id: "debt_gdp",
        connector_id: "c1",
        access_mode: "python_lib",
        spec: { method: "x.y" },
        canary_value: { value: 1 },
        canary_at: null,
        created_at: null,
        updated_at: null,
      },
      {
        id: "rcs-2",
        department_id: "retail_sentiment",
        need_id: "social_volume",
        connector_id: "c2",
        access_mode: "remote_mcp",
        spec: { tool_name: "lookup" },
        canary_value: null,
        canary_at: null,
        created_at: null,
        updated_at: null,
      },
    ]);

    render(<RunnerCallableSpecsAdminPanel />);
    await waitFor(() =>
      expect(mocked.listRunnerSpecs).toHaveBeenCalled(),
    );
    expect(screen.getByText("macro_research")).toBeInTheDocument();
    expect(screen.getByText("retail_sentiment")).toBeInTheDocument();
    expect(screen.getByText(/need: debt_gdp/)).toBeInTheDocument();
    expect(screen.getByText(/need: social_volume/)).toBeInTheDocument();
  });

  it("Re-resolve calls reResolveSpecs with the row's connector_id", async () => {
    mocked.listRunnerSpecs.mockResolvedValue([
      {
        id: "rcs-1",
        department_id: "macro_research",
        need_id: "debt_gdp",
        connector_id: "c1",
        access_mode: "python_lib",
        spec: {},
        canary_value: null,
        canary_at: null,
        created_at: null,
        updated_at: null,
      },
    ]);
    mockedConnectors.reResolveSpecs.mockResolvedValue([]);

    render(<RunnerCallableSpecsAdminPanel />);
    await screen.findByText("macro_research");
    fireEvent.click(screen.getByRole("button", { name: /re-resolve/i }));
    await waitFor(() =>
      expect(mockedConnectors.reResolveSpecs).toHaveBeenCalledWith("c1"),
    );
  });

  it("renders empty-state when there are no specs", async () => {
    mocked.listRunnerSpecs.mockResolvedValue([]);
    render(<RunnerCallableSpecsAdminPanel />);
    expect(
      await screen.findByText(/no resolved specs yet/i),
    ).toBeInTheDocument();
  });
});
