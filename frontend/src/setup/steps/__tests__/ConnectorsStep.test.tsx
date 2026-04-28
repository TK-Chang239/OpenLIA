import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { ConnectorsStep } from "../ConnectorsStep";
import * as connectorsApi from "../../../api/connectors";
import * as deptHealthApi from "../../../api/dept-health";
import type { ConnectorRow } from "../../../api/connectors";

vi.mock("../../../api/connectors", async () => {
  const actual = await vi.importActual<typeof connectorsApi>(
    "../../../api/connectors",
  );
  return {
    ...actual,
    listConnectors: vi.fn(),
    createConnector: vi.fn(),
    deleteConnector: vi.fn(),
    validateConnector: vi.fn(),
    listProposedSpecs: vi.fn(),
    reResolveSpecs: vi.fn(),
    approveSpec: vi.fn(),
  };
});

const mocked = connectorsApi as unknown as {
  listConnectors: ReturnType<typeof vi.fn>;
  createConnector: ReturnType<typeof vi.fn>;
  deleteConnector: ReturnType<typeof vi.fn>;
  validateConnector: ReturnType<typeof vi.fn>;
  listProposedSpecs: ReturnType<typeof vi.fn>;
  reResolveSpecs: ReturnType<typeof vi.fn>;
  approveSpec: ReturnType<typeof vi.fn>;
};

function row(overrides: Partial<ConnectorRow> = {}): ConnectorRow {
  return {
    id: "c1",
    provider_id: "eodhd",
    display_name: "EODHD",
    source: "remote_mcp",
    category: "financial",
    status: "validated",
    last_error: null,
    cached_tools_count: 0,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocked.listConnectors.mockResolvedValue([]);
  mocked.createConnector.mockResolvedValue(row());
  mocked.deleteConnector.mockResolvedValue(undefined);
  mocked.validateConnector.mockResolvedValue(row());
  mocked.listProposedSpecs.mockResolvedValue([]);
  mocked.reResolveSpecs.mockResolvedValue([]);
  mocked.approveSpec.mockResolvedValue({
    id: "rcs",
    department_id: "x",
    need_id: "y",
    connector_id: "c1",
    access_mode: "remote_mcp",
  });
  vi.spyOn(deptHealthApi, "fetchDeptHealth").mockResolvedValue([]);
});

describe("ConnectorsStep", () => {
  it("renders empty-state copy when no built-ins or connectors", async () => {
    render(
      <ConnectorsStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(
      await screen.findByText(/no built-in templates available/i),
    ).toBeInTheDocument();
    expect(
      await screen.findByText(/no connectors yet/i),
    ).toBeInTheDocument();
  });

  it("Next disabled when no validated connector", async () => {
    mocked.listConnectors.mockResolvedValue([
      row({ status: "pending" }),
    ]);
    render(
      <ConnectorsStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />,
    );
    await waitFor(() =>
      expect(mocked.listConnectors).toHaveBeenCalled(),
    );
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  it("Next enabled and onSaved invoked when a validated connector exists", async () => {
    mocked.listConnectors.mockResolvedValue([row({ status: "validated" })]);
    const onSaved = vi.fn();
    render(
      <ConnectorsStep totalSteps={5} onBack={vi.fn()} onSaved={onSaved} />,
    );
    const next = await screen.findByRole("button", { name: /next/i });
    await waitFor(() => expect(next).not.toBeDisabled());
    fireEvent.click(next);
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it("delete button calls deleteConnector(id)", async () => {
    mocked.listConnectors.mockResolvedValueOnce([row()]);
    mocked.listConnectors.mockResolvedValueOnce([]);
    render(
      <ConnectorsStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />,
    );
    await screen.findByText("EODHD");
    fireEvent.click(screen.getByRole("button", { name: /delete/i }));
    await waitFor(() => expect(mocked.deleteConnector).toHaveBeenCalledWith("c1"));
  });

  it("Add custom connector button toggles the form", async () => {
    render(
      <ConnectorsStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: /add custom connector/i }),
    );
    expect(await screen.findByLabelText(/^source$/i)).toBeInTheDocument();
  });

  it("Review specs button fetches proposals", async () => {
    mocked.listConnectors.mockResolvedValue([row()]);
    mocked.listProposedSpecs.mockResolvedValueOnce([]);
    render(
      <ConnectorsStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />,
    );
    await screen.findByText("EODHD");
    fireEvent.click(screen.getByRole("button", { name: /review specs/i }));
    await waitFor(() =>
      expect(mocked.listProposedSpecs).toHaveBeenCalledWith("c1"),
    );
    expect(
      await screen.findByText(/no proposals at this time/i),
    ).toBeInTheDocument();
  });
});
