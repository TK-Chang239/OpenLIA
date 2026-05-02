import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { ConnectorsStep } from "../ConnectorsStep";
import * as connectorsApi from "../../../api/connectors";
import * as deptHealthApi from "../../../api/dept-health";
import * as setupApi from "../../../api/setup";
import type { ConnectorRow } from "../../../api/connectors";
import { ApiError } from "../../../api/client";

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
    getConnector: vi.fn(),
    updateConnector: vi.fn(),
    listBuiltinTemplates: vi.fn(),
  };
});

vi.mock("../../../api/setup", async () => {
  const actual = await vi.importActual<typeof setupApi>("../../../api/setup");
  return {
    ...actual,
    saveProviders: vi.fn(),
  };
});

const mockedSetup = setupApi as unknown as {
  saveProviders: ReturnType<typeof vi.fn>;
};

const mocked = connectorsApi as unknown as {
  listConnectors: ReturnType<typeof vi.fn>;
  createConnector: ReturnType<typeof vi.fn>;
  deleteConnector: ReturnType<typeof vi.fn>;
  validateConnector: ReturnType<typeof vi.fn>;
  listProposedSpecs: ReturnType<typeof vi.fn>;
  reResolveSpecs: ReturnType<typeof vi.fn>;
  approveSpec: ReturnType<typeof vi.fn>;
  getConnector: ReturnType<typeof vi.fn>;
  updateConnector: ReturnType<typeof vi.fn>;
  listBuiltinTemplates: ReturnType<typeof vi.fn>;
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
  mockedSetup.saveProviders.mockResolvedValue({ ok: true });
  mocked.getConnector.mockResolvedValue({
    ...row(),
    launch: {
      modes: [
        {
          kind: "remote_mcp",
          url: "https://example.com/mcp",
          headers: { Authorization: "Bearer x" },
        },
      ],
    },
    secret_keys: [],
  });
  mocked.updateConnector.mockResolvedValue(row());
  mocked.listBuiltinTemplates.mockResolvedValue([]);
});

describe("ConnectorsStep", () => {
  it("renders empty-state copy when no connectors exist", async () => {
    render(
      <ConnectorsStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />,
    );
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
    await waitFor(() => expect(mockedSetup.saveProviders).toHaveBeenCalled());
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it("Next surfaces server detail.message when /setup/providers returns 422", async () => {
    mocked.listConnectors.mockResolvedValue([row({ status: "validated" })]);
    mockedSetup.saveProviders.mockRejectedValueOnce(
      new ApiError(422, "HTTP 422 on /api/setup/providers", {
        detail: {
          code: "no_validated_connector",
          message: "Add at least one connector and click Validate before continuing.",
        },
      }),
    );
    const onSaved = vi.fn();
    render(
      <ConnectorsStep totalSteps={5} onBack={vi.fn()} onSaved={onSaved} />,
    );
    const next = await screen.findByRole("button", { name: /next/i });
    await waitFor(() => expect(next).not.toBeDisabled());
    fireEvent.click(next);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        /Add at least one connector and click Validate before continuing\./,
      ),
    );
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("shows a hint when there are connectors but none validated", async () => {
    mocked.listConnectors.mockResolvedValue([row({ status: "pending" })]);
    render(
      <ConnectorsStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />,
    );
    await screen.findByText("EODHD");
    expect(screen.getByTestId("next-disabled-hint")).toHaveTextContent(
      /At least one connector must finish validating before you can continue\./,
    );
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

  it("Edit button fetches connector detail and shows form prefilled", async () => {
    mocked.listConnectors.mockResolvedValue([
      row({ status: "failed", last_error: "boom" }),
    ]);
    render(
      <ConnectorsStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />,
    );
    await screen.findByText("EODHD");

    fireEvent.click(screen.getByRole("button", { name: /^edit$/i }));

    await waitFor(() =>
      expect(mocked.getConnector).toHaveBeenCalledWith("c1"),
    );
    // Form appears with the existing URL prefilled
    const urlInput = (await screen.findByLabelText(/^url$/i)) as HTMLInputElement;
    expect(urlInput.value).toBe("https://example.com/mcp");
    // Save changes button is the edit-mode submit
    expect(
      screen.getByRole("button", { name: /save changes/i }),
    ).toBeInTheDocument();
  });

  it("renders the catalog grid when 'Add from catalog' is clicked", async () => {
    mocked.listBuiltinTemplates.mockResolvedValue([
      {
        template_id: "firecrawl",
        display_name: "Firecrawl",
        category: "web_search",
        api_key_env_var: "FIRECRAWL_API_KEY",
        covered_need_ids: [],
      },
    ]);
    render(
      <ConnectorsStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />,
    );
    fireEvent.click(await screen.findByRole("button", { name: /add from catalog/i }));
    expect(await screen.findByText("Firecrawl")).toBeInTheDocument();
  });

  it("opens the install form when a catalog card is clicked", async () => {
    mocked.listBuiltinTemplates.mockResolvedValue([
      {
        template_id: "firecrawl",
        display_name: "Firecrawl",
        category: "web_search",
        api_key_env_var: "FIRECRAWL_API_KEY",
        covered_need_ids: [],
      },
    ]);
    render(
      <ConnectorsStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />,
    );
    fireEvent.click(await screen.findByRole("button", { name: /add from catalog/i }));
    fireEvent.click(await screen.findByText("Firecrawl"));
    expect(await screen.findByLabelText(/api key/i)).toBeInTheDocument();
  });
});
