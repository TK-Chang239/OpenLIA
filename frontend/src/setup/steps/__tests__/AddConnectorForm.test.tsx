import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AddConnectorForm } from "../AddConnectorForm";
import * as connectorsApi from "../../../api/connectors";

vi.mock("../../../api/connectors", async () => {
  const actual = await vi.importActual<typeof connectorsApi>(
    "../../../api/connectors",
  );
  return {
    ...actual,
    createConnector: vi.fn(),
  };
});

const mocked = connectorsApi as unknown as {
  createConnector: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  vi.clearAllMocks();
  mocked.createConnector.mockResolvedValue({
    id: "c1",
    provider_id: "p",
    display_name: "p",
    source: "cli_mcp",
    category: "financial",
    status: "pending",
    last_error: null,
    cached_tools_count: 0,
  });
});

describe("AddConnectorForm", () => {
  it("populates argv, env keys, secrets, and provider id from a pasted MCP config JSON", async () => {
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={vi.fn()} />);

    const blob = JSON.stringify({
      mcpServers: {
        newsapi: {
          command: "npx",
          args: ["-y", "newsapi-mcp"],
          env: { NEWSAPI_KEY: "sk-test-123" },
        },
      },
    });

    fireEvent.change(screen.getByLabelText(/paste mcp config/i), {
      target: { value: blob },
    });

    expect(
      (screen.getByLabelText(/provider id/i) as HTMLInputElement).value,
    ).toBe("newsapi");
    expect(
      (screen.getByLabelText(/argv \(space-separated\)/i) as HTMLInputElement)
        .value,
    ).toBe("npx -y newsapi-mcp");
    expect(
      (screen.getByLabelText(/env keys \(comma-separated\)/i) as HTMLInputElement)
        .value,
    ).toBe("NEWSAPI_KEY");
    expect((screen.getByLabelText(/secret key 0/i) as HTMLInputElement).value).toBe(
      "NEWSAPI_KEY",
    );
    expect((screen.getByLabelText(/secret value 0/i) as HTMLInputElement).value).toBe(
      "sk-test-123",
    );
  });

  it("shows inline error and preserves manually-typed fields when pasted JSON is malformed", () => {
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={vi.fn()} />);

    fireEvent.change(screen.getByLabelText(/argv \(space-separated\)/i), {
      target: { value: "uvx already-typed" },
    });
    fireEvent.change(screen.getByLabelText(/paste mcp config/i), {
      target: { value: "{ not json" },
    });

    expect(screen.getByRole("alert").textContent).toMatch(/json|parse/i);
    expect(
      (screen.getByLabelText(/argv \(space-separated\)/i) as HTMLInputElement)
        .value,
    ).toBe("uvx already-typed");
  });

  it("submits cli_mcp with parsed argv list and env_keys", async () => {
    const onCreated = vi.fn();
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={onCreated} />);

    fireEvent.change(screen.getByLabelText(/provider id/i), {
      target: { value: "polygon-cli" },
    });
    fireEvent.change(screen.getByLabelText(/argv \(space-separated\)/i), {
      target: { value: "npx -y polygon-mcp" },
    });
    fireEvent.change(screen.getByLabelText(/env keys \(comma-separated\)/i), {
      target: { value: "POLYGON_API_KEY, OTHER" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create connector/i }));

    await waitFor(() => expect(mocked.createConnector).toHaveBeenCalled());
    const call = mocked.createConnector.mock.calls[0][0];
    expect(call).toMatchObject({
      provider_id: "polygon-cli",
      source: "cli_mcp",
      category: "financial",
      launch: {
        modes: [
          {
            kind: "cli_mcp",
            argv: ["npx", "-y", "polygon-mcp"],
            env_keys: ["POLYGON_API_KEY", "OTHER"],
          },
        ],
      },
    });
    expect(onCreated).toHaveBeenCalled();
  });

  it("submits remote_mcp with url and headers", async () => {
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/^source$/i), {
      target: { value: "remote_mcp" },
    });
    fireEvent.change(screen.getByLabelText(/provider id/i), {
      target: { value: "rmcp" },
    });
    fireEvent.change(screen.getByLabelText(/^url$/i), {
      target: { value: "https://example.com/sse" },
    });
    fireEvent.change(screen.getByLabelText(/header key 0/i), {
      target: { value: "Authorization" },
    });
    fireEvent.change(screen.getByLabelText(/header value 0/i), {
      target: { value: "Bearer x" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create connector/i }));
    await waitFor(() => expect(mocked.createConnector).toHaveBeenCalled());
    const call = mocked.createConnector.mock.calls[0][0];
    expect(call.source).toBe("remote_mcp");
    expect(call.launch.modes[0]).toMatchObject({
      kind: "remote_mcp",
      url: "https://example.com/sse",
      headers: { Authorization: "Bearer x" },
    });
  });

  it("submits python_lib with instance_factory cls + args", async () => {
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/^source$/i), {
      target: { value: "python_lib" },
    });
    fireEvent.change(screen.getByLabelText(/provider id/i), {
      target: { value: "eodhd" },
    });
    fireEvent.change(screen.getByLabelText(/pip name/i), {
      target: { value: "eodhd" },
    });
    fireEvent.change(screen.getByLabelText(/import module/i), {
      target: { value: "eodhd" },
    });
    fireEvent.change(screen.getByLabelText(/instance factory class/i), {
      target: { value: "APIClient" },
    });
    fireEvent.change(screen.getByLabelText(/instance factory args/i), {
      target: { value: '{"api_token": "${EODHD_API_KEY}"}' },
    });

    fireEvent.click(screen.getByRole("button", { name: /create connector/i }));
    await waitFor(() => expect(mocked.createConnector).toHaveBeenCalled());
    const call = mocked.createConnector.mock.calls[0][0];
    expect(call.source).toBe("python_lib");
    expect(call.launch.modes[0]).toMatchObject({
      kind: "python_lib",
      pip_name: "eodhd",
      import_module: "eodhd",
      instance_factory: { cls: "APIClient", args: { api_token: "${EODHD_API_KEY}" } },
    });
  });

  it("includes secrets in the payload", async () => {
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/provider id/i), {
      target: { value: "x" },
    });
    fireEvent.change(screen.getByLabelText(/argv \(space-separated\)/i), {
      target: { value: "x" },
    });
    fireEvent.change(screen.getByLabelText(/secret key 0/i), {
      target: { value: "MY_KEY" },
    });
    fireEvent.change(screen.getByLabelText(/secret value 0/i), {
      target: { value: "v" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create connector/i }));
    await waitFor(() => expect(mocked.createConnector).toHaveBeenCalled());
    const call = mocked.createConnector.mock.calls[0][0];
    expect(call.secrets).toEqual({ MY_KEY: "v" });
  });

  it("cancel calls onCancel", () => {
    const onCancel = vi.fn();
    render(<AddConnectorForm onCancel={onCancel} onCreated={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalled();
  });
});
