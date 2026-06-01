import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { ConnectorsSection } from "../ConnectorsSection";
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
    listBuiltinTemplates: vi.fn(),
    createConnector: vi.fn(),
  };
});

const mocked = connectorsApi as unknown as {
  listConnectors: ReturnType<typeof vi.fn>;
  deleteConnector: ReturnType<typeof vi.fn>;
  validateConnector: ReturnType<typeof vi.fn>;
  listBuiltinTemplates: ReturnType<typeof vi.fn>;
  createConnector: ReturnType<typeof vi.fn>;
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
  mocked.listBuiltinTemplates.mockResolvedValue([]);
  mocked.createConnector.mockResolvedValue(row());
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
});
