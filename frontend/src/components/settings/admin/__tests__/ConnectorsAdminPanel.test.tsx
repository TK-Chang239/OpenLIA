import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { ConnectorsAdminPanel } from "../ConnectorsAdminPanel";
import * as connectorsApi from "../../../../api/connectors";
import * as deptHealthApi from "../../../../api/dept-health";
import type { ConnectorRow } from "../../../../api/connectors";

vi.mock("../../../../api/connectors", async () => {
  const actual = await vi.importActual<typeof connectorsApi>(
    "../../../../api/connectors",
  );
  return {
    ...actual,
    listConnectors: vi.fn(),
    deleteConnector: vi.fn(),
    validateConnector: vi.fn(),
  };
});

const mocked = connectorsApi as unknown as {
  listConnectors: ReturnType<typeof vi.fn>;
  deleteConnector: ReturnType<typeof vi.fn>;
  validateConnector: ReturnType<typeof vi.fn>;
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
  mocked.listConnectors.mockResolvedValue([row()]);
  mocked.deleteConnector.mockResolvedValue(undefined);
  mocked.validateConnector.mockResolvedValue(row());
  vi.spyOn(deptHealthApi, "fetchDeptHealth").mockResolvedValue([]);
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("ConnectorsAdminPanel", () => {
  it("renders connector rows", async () => {
    render(<ConnectorsAdminPanel />);
    expect(await screen.findByText("EODHD")).toBeInTheDocument();
    expect(screen.getByText("eodhd")).toBeInTheDocument();
    expect(screen.getByText("validated")).toBeInTheDocument();
  });

  it("Validate now triggers validateConnector(id)", async () => {
    render(<ConnectorsAdminPanel />);
    await screen.findByText("EODHD");
    fireEvent.click(screen.getByRole("button", { name: /validate now/i }));
    await waitFor(() =>
      expect(mocked.validateConnector).toHaveBeenCalledWith("c1"),
    );
  });

  it("Delete triggers deleteConnector(id) after confirm", async () => {
    render(<ConnectorsAdminPanel />);
    await screen.findByText("EODHD");
    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));
    await waitFor(() =>
      expect(mocked.deleteConnector).toHaveBeenCalledWith("c1"),
    );
  });

  it("Edit opens a modal that disallows changing source/category", async () => {
    render(<ConnectorsAdminPanel />);
    await screen.findByText("EODHD");
    fireEvent.click(screen.getByRole("button", { name: /^edit$/i }));
    expect(
      await screen.findByRole("dialog", { name: /edit connector/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/source \(remote_mcp\) and category \(financial\) are read-only/i),
    ).toBeInTheDocument();
  });

  it("renders empty-state copy when no connectors exist", async () => {
    mocked.listConnectors.mockResolvedValue([]);
    render(<ConnectorsAdminPanel />);
    expect(
      await screen.findByText(/no connectors configured/i),
    ).toBeInTheDocument();
  });
});
