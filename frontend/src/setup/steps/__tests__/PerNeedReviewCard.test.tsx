import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PerNeedReviewCard } from "../PerNeedReviewCard";
import * as connectorsApi from "../../../api/connectors";
import * as deptHealthApi from "../../../api/dept-health";
import type { ProposedSpec } from "../../../api/connectors";

vi.mock("../../../api/connectors", async () => {
  const actual = await vi.importActual<typeof connectorsApi>(
    "../../../api/connectors",
  );
  return {
    ...actual,
    approveSpec: vi.fn(),
    reResolveSpecs: vi.fn(),
  };
});

const mocked = connectorsApi as unknown as {
  approveSpec: ReturnType<typeof vi.fn>;
  reResolveSpecs: ReturnType<typeof vi.fn>;
};

const PROPOSAL: ProposedSpec = {
  department_id: "macro_research",
  need_id: "debt_gdp",
  proposed_spec: {
    method: "eodhd.APIClient.economic_data",
    param_bindings: { country: "country_code", indicator: "DEBT_GDP_PCT" },
  },
  canary_value: { value: 122.4 },
  canary_ok: true,
  shape_match: true,
  error: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocked.approveSpec.mockResolvedValue({
    id: "rcs",
    department_id: "macro_research",
    need_id: "debt_gdp",
    connector_id: "c1",
    access_mode: "python_lib",
  });
  mocked.reResolveSpecs.mockResolvedValue([PROPOSAL]);
  vi.spyOn(deptHealthApi, "fetchDeptHealth").mockResolvedValue([]);
});

describe("PerNeedReviewCard", () => {
  it("renders department, need, callee, bindings and canary", () => {
    render(
      <PerNeedReviewCard
        connectorId="c1"
        proposal={PROPOSAL}
        onChanged={vi.fn()}
      />,
    );
    expect(screen.getByText("macro_research")).toBeInTheDocument();
    expect(screen.getByText(/need: debt_gdp/)).toBeInTheDocument();
    expect(
      screen.getByText("eodhd.APIClient.economic_data"),
    ).toBeInTheDocument();
    expect(screen.getByText("country")).toBeInTheDocument();
    expect(screen.getByText('"country_code"')).toBeInTheDocument();
    // Canary value is rendered as JSON pretty-print.
    expect(screen.getByText(/122\.4/)).toBeInTheDocument();
  });

  it("Approve button calls approveSpec(connectorId, dept, need)", async () => {
    const onChanged = vi.fn();
    render(
      <PerNeedReviewCard
        connectorId="c1"
        proposal={PROPOSAL}
        onChanged={onChanged}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /approve/i }));
    await waitFor(() =>
      expect(mocked.approveSpec).toHaveBeenCalledWith(
        "c1",
        "macro_research",
        "debt_gdp",
      ),
    );
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
  });

  it("Re-resolve button calls reResolveSpecs(connectorId)", async () => {
    render(
      <PerNeedReviewCard
        connectorId="c1"
        proposal={PROPOSAL}
        onChanged={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /re-resolve/i }));
    await waitFor(() =>
      expect(mocked.reResolveSpecs).toHaveBeenCalledWith("c1"),
    );
  });

  it("Try-different button calls onTryDifferent when provided", () => {
    const onTry = vi.fn();
    render(
      <PerNeedReviewCard
        connectorId="c1"
        proposal={PROPOSAL}
        onChanged={vi.fn()}
        onTryDifferent={onTry}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /try a different connector/i }),
    );
    expect(onTry).toHaveBeenCalled();
  });
});
