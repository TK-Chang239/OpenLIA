import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { ConnectorsSection } from "../ConnectorsSection";
import * as connectorsApi from "../../../../api/connectors";
import * as deptHealthApi from "../../../../api/dept-health";
import type { ConnectorDetail, ConnectorRow } from "../../../../api/connectors";

vi.mock("../../../../api/connectors", async () => {
  const actual = await vi.importActual<typeof connectorsApi>(
    "../../../../api/connectors",
  );
  return {
    ...actual,
    listConnectors: vi.fn(),
    deleteConnector: vi.fn(),
    validateConnector: vi.fn(),
    listBuiltinTemplates: vi.fn(),
    createConnector: vi.fn(),
    getConnector: vi.fn(),
    updateConnector: vi.fn(),
  };
});

const mocked = connectorsApi as unknown as {
  listConnectors: ReturnType<typeof vi.fn>;
  deleteConnector: ReturnType<typeof vi.fn>;
  validateConnector: ReturnType<typeof vi.fn>;
  listBuiltinTemplates: ReturnType<typeof vi.fn>;
  createConnector: ReturnType<typeof vi.fn>;
  getConnector: ReturnType<typeof vi.fn>;
  updateConnector: ReturnType<typeof vi.fn>;
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

function detail(overrides: Partial<ConnectorDetail> = {}): ConnectorDetail {
  return {
    ...row(),
    launch: { modes: [{ kind: "remote_mcp", url: "https://mcp.eodhd.com" }] },
    secret_keys: ["EODHD_API_KEY"],
    source_repo_url: null,
    source_repo_revision: null,
    grounding_paths: null,
    openapi_url: null,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocked.listConnectors.mockResolvedValue([row()]);
  mocked.deleteConnector.mockResolvedValue(undefined);
  mocked.validateConnector.mockResolvedValue(row());
  mocked.listBuiltinTemplates.mockResolvedValue([]);
  mocked.createConnector.mockResolvedValue(row());
  mocked.getConnector.mockResolvedValue(detail());
  mocked.updateConnector.mockResolvedValue(row());
  vi.spyOn(deptHealthApi, "fetchDeptHealth").mockResolvedValue([]);
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("ConnectorsSection", () => {
  it("renders connector rows", async () => {
    render(<ConnectorsSection />);
    expect(await screen.findByText("EODHD")).toBeInTheDocument();
    expect(screen.getByText("eodhd")).toBeInTheDocument();
    expect(screen.getByText("validated")).toBeInTheDocument();
  });

  it("Validate now triggers validateConnector(id)", async () => {
    render(<ConnectorsSection />);
    await screen.findByText("EODHD");
    fireEvent.click(screen.getByRole("button", { name: /validate now/i }));
    await waitFor(() =>
      expect(mocked.validateConnector).toHaveBeenCalledWith("c1"),
    );
  });

  it("Delete triggers deleteConnector(id) after confirm", async () => {
    render(<ConnectorsSection />);
    await screen.findByText("EODHD");
    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));
    await waitFor(() =>
      expect(mocked.deleteConnector).toHaveBeenCalledWith("c1"),
    );
  });

  it("Edit opens a modal that disallows changing source/category", async () => {
    render(<ConnectorsSection />);
    await screen.findByText("EODHD");
    fireEvent.click(screen.getByRole("button", { name: /^edit$/i }));
    expect(
      await screen.findByRole("dialog", { name: /edit connector/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/source \(remote_mcp\) and category \(financial\) are read-only/i),
    ).toBeInTheDocument();
  });

  it("Edit save PUTs the full connector with the edited name, preserving secrets", async () => {
    render(<ConnectorsSection />);
    await screen.findByText("EODHD");
    fireEvent.click(screen.getByRole("button", { name: /^edit$/i }));
    await screen.findByRole("dialog", { name: /edit connector/i });
    // getConnector supplies the launch config the PUT must round-trip.
    await waitFor(() => expect(mocked.getConnector).toHaveBeenCalledWith("c1"));
    // existing secret keys are surfaced as a hint
    expect(screen.getByText(/EODHD_API_KEY/)).toBeInTheDocument();

    const nameInput = screen.getByDisplayValue("EODHD");
    fireEvent.change(nameInput, { target: { value: "EODHD Prod" } });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => expect(mocked.updateConnector).toHaveBeenCalledTimes(1));
    const [id, input] = mocked.updateConnector.mock.calls[0];
    expect(id).toBe("c1");
    expect(input).toMatchObject({
      provider_id: "eodhd",
      display_name: "EODHD Prod",
      source: "remote_mcp",
      category: "financial",
      launch: { modes: [{ kind: "remote_mcp", url: "https://mcp.eodhd.com" }] },
    });
    // no new secrets entered -> field omitted so the server keeps existing ones
    expect(input.secrets).toBeUndefined();
  });

  it("Edit save includes secrets only when the user enters them", async () => {
    render(<ConnectorsSection />);
    await screen.findByText("EODHD");
    fireEvent.click(screen.getByRole("button", { name: /^edit$/i }));
    await screen.findByRole("dialog", { name: /edit connector/i });
    await waitFor(() => expect(mocked.getConnector).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText("secret key 0"), {
      target: { value: "EODHD_API_KEY" },
    });
    fireEvent.change(screen.getByLabelText("secret value 0"), {
      target: { value: "new-secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => expect(mocked.updateConnector).toHaveBeenCalledTimes(1));
    const [, input] = mocked.updateConnector.mock.calls[0];
    expect(input.secrets).toEqual({ EODHD_API_KEY: "new-secret" });
  });

  it("Edit surfaces the server error when the save re-validation fails", async () => {
    mocked.updateConnector.mockResolvedValue(
      row({ status: "failed", last_error: "bad key" }),
    );
    render(<ConnectorsSection />);
    await screen.findByText("EODHD");
    fireEvent.click(screen.getByRole("button", { name: /^edit$/i }));
    await screen.findByRole("dialog", { name: /edit connector/i });
    await waitFor(() => expect(mocked.getConnector).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/bad key/i);
  });

  it("renders empty-state copy when no connectors exist", async () => {
    mocked.listConnectors.mockResolvedValue([]);
    render(<ConnectorsSection />);
    expect(
      await screen.findByText(/no connectors configured/i),
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
    render(<ConnectorsSection />);
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
    render(<ConnectorsSection />);
    fireEvent.click(await screen.findByRole("button", { name: /add from catalog/i }));
    fireEvent.click(await screen.findByText("Firecrawl"));
    expect(await screen.findByLabelText(/api key/i)).toBeInTheDocument();
  });

  it("shows the smart-paste box as the always-visible primary add path", async () => {
    render(<ConnectorsSection />);
    // Smart-paste textarea is present on mount, with no toggle button to reveal it.
    expect(
      await screen.findByLabelText(/paste a url or command/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /add mcp connector/i }),
    ).toBeNull();
  });

  it("resets the smart-paste form after a successful add", async () => {
    render(<ConnectorsSection />);
    const box = (await screen.findByLabelText(
      /paste a url or command/i,
    )) as HTMLTextAreaElement;
    fireEvent.change(box, {
      target: { value: "https://mcp.alphavantage.co/mcp?apikey=AV12345" },
    });
    expect(box.value).toContain("alphavantage");
    fireEvent.click(screen.getByRole("button", { name: /validate & add/i }));
    await waitFor(() => expect(mocked.createConnector).toHaveBeenCalledTimes(1));
    // After onCreated, the formNonce key change remounts the form -> textarea is empty.
    await waitFor(() =>
      expect(
        (screen.getByLabelText(/paste a url or command/i) as HTMLTextAreaElement)
          .value,
      ).toBe(""),
    );
  });

  it("reveals the advanced form when the 'advanced' secondary link is clicked", async () => {
    render(<ConnectorsSection />);
    await screen.findByText("EODHD");
    fireEvent.click(
      screen.getByRole("button", { name: /add connector \(advanced\)/i }),
    );
    // AddConnectorForm has a "source" select that the smart-paste form lacks.
    expect(await screen.findByLabelText("source")).toBeInTheDocument();
  });
});
