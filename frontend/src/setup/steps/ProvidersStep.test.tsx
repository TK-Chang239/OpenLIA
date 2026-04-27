import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { ProvidersStep } from "./ProvidersStep";
import * as connectorsApi from "../../api/connectors";
import type { ConnectorRow } from "../../api/connectors";

vi.mock("../../api/connectors", async () => {
  const actual = await vi.importActual<typeof connectorsApi>("../../api/connectors");
  return {
    ...actual,
    listConnectors: vi.fn(),
    createConnector: vi.fn(),
    deleteConnector: vi.fn(),
    revalidateConnector: vi.fn(),
  };
});

const mocked = connectorsApi as unknown as {
  listConnectors: ReturnType<typeof vi.fn>;
  createConnector: ReturnType<typeof vi.fn>;
  deleteConnector: ReturnType<typeof vi.fn>;
  revalidateConnector: ReturnType<typeof vi.fn>;
};

function row(overrides: Partial<ConnectorRow> = {}): ConnectorRow {
  return {
    id: "c1",
    provider_id: "eodhd",
    source: "built_in",
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
  mocked.revalidateConnector.mockResolvedValue(row());
});

describe("ProvidersStep", () => {
  it("renders 4 category tabs", async () => {
    render(<ProvidersStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />);
    await waitFor(() => expect(screen.getByRole("tablist")).toBeInTheDocument());
    expect(screen.getByRole("tab", { name: /financial/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /news/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /social/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /web search/i })).toBeInTheDocument();
  });

  it("renders connector rows under the active category tab", async () => {
    mocked.listConnectors.mockResolvedValue([
      row({ id: "c1", provider_id: "eodhd", category: "financial" }),
      row({ id: "c2", provider_id: "newsapi_ai", category: "news", status: "pending" }),
    ]);

    render(<ProvidersStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />);
    await waitFor(() => expect(mocked.listConnectors).toHaveBeenCalled());

    // Financial tab is the default
    expect(await screen.findByText("eodhd")).toBeInTheDocument();
    expect(screen.queryByText("newsapi_ai")).not.toBeInTheDocument();

    // Switch to news tab
    fireEvent.click(screen.getByRole("tab", { name: /news/i }));
    expect(await screen.findByText("newsapi_ai")).toBeInTheDocument();
  });

  it("Next disabled until ≥1 financial AND ≥1 news connector validated", async () => {
    mocked.listConnectors.mockResolvedValue([
      row({ id: "c1", provider_id: "eodhd", category: "financial", status: "validated" }),
    ]);

    render(<ProvidersStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />);
    await waitFor(() => expect(mocked.listConnectors).toHaveBeenCalled());
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  it("Next enabled and onSaved called when both required categories validated", async () => {
    mocked.listConnectors.mockResolvedValue([
      row({ id: "c1", provider_id: "eodhd", category: "financial", status: "validated" }),
      row({ id: "c2", provider_id: "newsapi_ai", category: "news", status: "validated" }),
    ]);
    const onSaved = vi.fn();
    render(<ProvidersStep totalSteps={5} onBack={vi.fn()} onSaved={onSaved} />);
    await waitFor(() => expect(mocked.listConnectors).toHaveBeenCalled());

    const nextBtn = await screen.findByRole("button", { name: /next/i });
    await waitFor(() => expect(nextBtn).not.toBeDisabled());
    fireEvent.click(nextBtn);
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it("delete button calls deleteConnector(id) and refreshes", async () => {
    mocked.listConnectors.mockResolvedValueOnce([
      row({ id: "c1", provider_id: "eodhd", category: "financial" }),
    ]);
    mocked.listConnectors.mockResolvedValueOnce([]);

    render(<ProvidersStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />);
    await screen.findByText("eodhd");

    fireEvent.click(screen.getByRole("button", { name: /remove provider/i }));
    await waitFor(() => expect(mocked.deleteConnector).toHaveBeenCalledWith("c1"));
    await waitFor(() => expect(mocked.listConnectors).toHaveBeenCalledTimes(2));
  });

  it("retest button calls revalidateConnector(id)", async () => {
    mocked.listConnectors.mockResolvedValue([
      row({ id: "c1", provider_id: "eodhd", category: "financial" }),
    ]);

    render(<ProvidersStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />);
    await screen.findByText("eodhd");

    fireEvent.click(screen.getByRole("button", { name: /retest provider/i }));
    await waitFor(() => expect(mocked.revalidateConnector).toHaveBeenCalledWith("c1"));
  });

  it("submit built-in path calls createConnector with correct payload", async () => {
    mocked.listConnectors.mockResolvedValue([]);
    render(<ProvidersStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />);
    await waitFor(() => expect(mocked.listConnectors).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /add financial provider/i }));

    // Built-in radio is selected by default; pick template + api key
    const select = await screen.findByRole("combobox");
    fireEvent.change(select, { target: { value: "eodhd" } });
    const apiKey = screen.getByLabelText(/api key/i);
    fireEvent.change(apiKey, { target: { value: "secret-key" } });

    fireEvent.click(screen.getByRole("button", { name: /test & save/i }));

    await waitFor(() => expect(mocked.createConnector).toHaveBeenCalled());
    const call = mocked.createConnector.mock.calls[0][0];
    expect(call).toMatchObject({
      provider_id: "eodhd",
      source: "built_in",
      category: "financial",
      launch: { kind: "built_in", template_id: "eodhd" },
      credentials_ref: "secret-key",
    });
  });

  it("submit remote_mcp path calls createConnector with remote launch", async () => {
    mocked.listConnectors.mockResolvedValue([]);
    render(<ProvidersStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />);
    await waitFor(() => expect(mocked.listConnectors).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /add financial provider/i }));

    const radioGroup = await screen.findByRole("radiogroup");
    fireEvent.click(within(radioGroup).getByLabelText(/remote mcp/i));

    fireEvent.change(screen.getByPlaceholderText(/example\.com\/mcp/i), {
      target: { value: "https://mcp.example.com/sse" },
    });
    fireEvent.click(screen.getByRole("button", { name: /test & save/i }));

    await waitFor(() => expect(mocked.createConnector).toHaveBeenCalled());
    const call = mocked.createConnector.mock.calls[0][0];
    expect(call.source).toBe("remote_mcp");
    expect(call.launch).toMatchObject({
      kind: "remote_mcp",
      url: "https://mcp.example.com/sse",
    });
  });

  it("submit cli_mcp path calls createConnector with argv array", async () => {
    mocked.listConnectors.mockResolvedValue([]);
    render(<ProvidersStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />);
    await waitFor(() => expect(mocked.listConnectors).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /add financial provider/i }));

    const radioGroup = await screen.findByRole("radiogroup");
    fireEvent.click(within(radioGroup).getByLabelText(/cli install/i));

    fireEvent.change(screen.getByPlaceholderText("my-mcp-server"), {
      target: { value: "polygon-cli" },
    });
    fireEvent.change(screen.getByPlaceholderText("npx -y my-mcp-server"), {
      target: { value: "npx -y polygon-mcp" },
    });

    fireEvent.click(screen.getByRole("button", { name: /test & save/i }));

    await waitFor(() => expect(mocked.createConnector).toHaveBeenCalled());
    const call = mocked.createConnector.mock.calls[0][0];
    expect(call).toMatchObject({
      provider_id: "polygon-cli",
      source: "cli_mcp",
      category: "financial",
      launch: { kind: "cli_mcp", argv: ["npx", "-y", "polygon-mcp"] },
    });
  });
});
