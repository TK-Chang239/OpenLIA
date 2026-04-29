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
    updateConnector: vi.fn(),
    introspectPythonLib: vi.fn(),
    installPythonPackage: vi.fn(),
  };
});

const mocked = connectorsApi as unknown as {
  createConnector: ReturnType<typeof vi.fn>;
  updateConnector: ReturnType<typeof vi.fn>;
  introspectPythonLib: ReturnType<typeof vi.fn>;
  installPythonPackage: ReturnType<typeof vi.fn>;
};

const STUB_ROW = {
  id: "c1",
  provider_id: "p",
  display_name: "p",
  source: "cli_mcp" as const,
  category: "financial" as const,
  status: "pending" as const,
  last_error: null,
  cached_tools_count: 0,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocked.createConnector.mockResolvedValue(STUB_ROW);
  mocked.updateConnector.mockResolvedValue(STUB_ROW);
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

  it("populates argv and provider id from a pasted bare npx command", () => {
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={vi.fn()} />);

    fireEvent.change(screen.getByLabelText(/paste mcp config/i), {
      target: { value: "npx -y newsapi-mcp" },
    });

    expect(
      (screen.getByLabelText(/provider id/i) as HTMLInputElement).value,
    ).toBe("newsapi");
    expect(
      (screen.getByLabelText(/argv \(space-separated\)/i) as HTMLInputElement)
        .value,
    ).toBe("npx -y newsapi-mcp");
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
    fireEvent.change(screen.getByLabelText(/main client class/i), {
      target: { value: "APIClient" },
    });
    fireEvent.change(screen.getByLabelText(/constructor settings/i), {
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

  it("Install package calls installPythonPackage with the typed pip name + version", async () => {
    mocked.installPythonPackage.mockResolvedValue({
      stdout: "Successfully installed eodhd-1.2.3",
    });
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/^source$/i), {
      target: { value: "python_lib" },
    });
    fireEvent.change(screen.getByLabelText(/pip name/i), {
      target: { value: "eodhd" },
    });
    fireEvent.change(screen.getByLabelText(/pip version/i), {
      target: { value: "==1.2.3" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /install package/i }),
    );
    await waitFor(() =>
      expect(mocked.installPythonPackage).toHaveBeenCalledWith(
        "eodhd",
        "==1.2.3",
      ),
    );
    expect(
      (await screen.findByTestId("install-status")).textContent,
    ).toMatch(/Successfully installed/);
  });

  it("Install package surfaces backend error inline", async () => {
    mocked.installPythonPackage.mockRejectedValue(
      new Error(
        "HTTP 400: ERROR: Could not find a version that satisfies eodhd==999",
      ),
    );
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/^source$/i), {
      target: { value: "python_lib" },
    });
    fireEvent.change(screen.getByLabelText(/pip name/i), {
      target: { value: "eodhd" },
    });
    fireEvent.change(screen.getByLabelText(/pip version/i), {
      target: { value: "==999" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /install package/i }),
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("install-error").textContent,
      ).toMatch(/Could not find a version/i),
    );
  });

  it("Detect parameters fills constructor JSON with kwarg names + secret refs", async () => {
    mocked.introspectPythonLib.mockResolvedValue({
      params: [{ name: "api_key", type: "str", required: true, default: null }],
    });
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/^source$/i), {
      target: { value: "python_lib" },
    });
    fireEvent.change(screen.getByLabelText(/import module/i), {
      target: { value: "eodhd" },
    });
    fireEvent.change(screen.getByLabelText(/main client class/i), {
      target: { value: "APIClient" },
    });

    fireEvent.click(
      screen.getByRole("button", { name: /detect parameters/i }),
    );

    await waitFor(() =>
      expect(mocked.introspectPythonLib).toHaveBeenCalledWith(
        "eodhd",
        "APIClient",
      ),
    );
    const argsField = (await screen.findByLabelText(
      /constructor settings/i,
    )) as HTMLTextAreaElement;
    const parsed = JSON.parse(argsField.value);
    expect(parsed).toEqual({ api_key: "$API_KEY" });
    // Secret row prefilled with the matching key
    expect(
      (screen.getByLabelText(/secret key 0/i) as HTMLInputElement).value,
    ).toBe("API_KEY");
  });

  it("Detect parameters treats credential-named optional kwargs as secrets and shows a status", async () => {
    // Mirrors EventRegistry.__init__: apiKey defaults to None so
    // inspect.signature reports required=False — but it still IS the secret.
    mocked.introspectPythonLib.mockResolvedValue({
      params: [
        { name: "apiKey", type: "Optional", required: false, default: null },
        { name: "host", type: "Optional", required: false, default: null },
        { name: "minDelayBetweenRequests", type: "float", required: false, default: 0.5 },
      ],
    });
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/^source$/i), {
      target: { value: "python_lib" },
    });
    fireEvent.change(screen.getByLabelText(/import module/i), {
      target: { value: "eventregistry" },
    });
    fireEvent.change(screen.getByLabelText(/main client class/i), {
      target: { value: "EventRegistry" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /detect parameters/i }),
    );
    const argsField = (await screen.findByLabelText(
      /constructor settings/i,
    )) as HTMLTextAreaElement;
    await waitFor(() => expect(argsField.value.length).toBeGreaterThan(0));
    const parsed = JSON.parse(argsField.value);
    expect(parsed.apiKey).toBe("$APIKEY");
    expect(parsed.minDelayBetweenRequests).toBe(0.5);
    expect(
      (screen.getByLabelText(/secret key 0/i) as HTMLInputElement).value,
    ).toBe("APIKEY");
    expect(screen.getByTestId("detect-status").textContent).toMatch(
      /3 parameters.*1 secret/i,
    );
  });

  it("Detect parameters surfaces a backend error inline", async () => {
    mocked.introspectPythonLib.mockRejectedValue(
      new Error(
        "HTTP 400: Module 'eodhd' is not installed in the server's Python environment...",
      ),
    );
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/^source$/i), {
      target: { value: "python_lib" },
    });
    fireEvent.change(screen.getByLabelText(/import module/i), {
      target: { value: "eodhd" },
    });
    fireEvent.change(screen.getByLabelText(/main client class/i), {
      target: { value: "APIClient" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /detect parameters/i }),
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("detect-error").textContent,
      ).toMatch(/not installed/i),
    );
  });

  it("populates pip name, version, and import module from a pasted pip command", () => {
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/^source$/i), {
      target: { value: "python_lib" },
    });

    fireEvent.change(screen.getByLabelText(/paste pip install command/i), {
      target: { value: "python3 -m pip install eodhd==1.2.3 -U" },
    });

    expect((screen.getByLabelText(/pip name/i) as HTMLInputElement).value).toBe(
      "eodhd",
    );
    expect(
      (screen.getByLabelText(/pip version/i) as HTMLInputElement).value,
    ).toBe("==1.2.3");
    expect(
      (screen.getByLabelText(/import module/i) as HTMLInputElement).value,
    ).toBe("eodhd");
  });

  it("shows inline error when pasted pip command is malformed", () => {
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/^source$/i), {
      target: { value: "python_lib" },
    });

    fireEvent.change(screen.getByLabelText(/pip name/i), {
      target: { value: "already-typed" },
    });
    fireEvent.change(screen.getByLabelText(/paste pip install command/i), {
      target: { value: "pip uninstall eodhd" },
    });

    expect(screen.getByRole("alert").textContent).toMatch(/install/i);
    expect((screen.getByLabelText(/pip name/i) as HTMLInputElement).value).toBe(
      "already-typed",
    );
  });

  it("shows hint text under provider id explaining its purpose", () => {
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={vi.fn()} />);
    expect(
      screen.getByTestId("hint-provider-id").textContent,
    ).toMatch(/identifier/i);
  });

  it("shows hint text under python_lib constructor settings explaining placeholders", () => {
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/^source$/i), {
      target: { value: "python_lib" },
    });
    expect(
      screen.getByTestId("hint-factory-args").textContent,
    ).toMatch(/\$/);
  });

  it("shows hint that OAuth is not supported for remote MCP servers", () => {
    render(<AddConnectorForm onCancel={vi.fn()} onCreated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/^source$/i), {
      target: { value: "remote_mcp" },
    });
    expect(
      screen.getByTestId("hint-remote-oauth").textContent,
    ).toMatch(/oauth is not supported/i);
    expect(
      screen.getByTestId("hint-remote-oauth").textContent,
    ).toMatch(/api_token|api key/i);
  });

  it("prefills fields from existing connector when editing", () => {
    render(
      <AddConnectorForm
        onCancel={vi.fn()}
        onCreated={vi.fn()}
        editing={{
          id: "c-123",
          providerId: "polygon",
          displayName: "Polygon",
          source: "cli_mcp",
          category: "financial",
          launch: {
            modes: [
              {
                kind: "cli_mcp",
                argv: ["npx", "-y", "polygon-mcp"],
                env_keys: ["POLYGON_API_KEY"],
              },
            ],
          },
          secretKeys: ["POLYGON_API_KEY"],
        }}
      />,
    );
    expect(
      (screen.getByLabelText(/provider id/i) as HTMLInputElement).value,
    ).toBe("polygon");
    expect(
      (screen.getByLabelText(/argv \(space-separated\)/i) as HTMLInputElement)
        .value,
    ).toBe("npx -y polygon-mcp");
    expect(
      (screen.getByLabelText(/env keys \(comma-separated\)/i) as HTMLInputElement)
        .value,
    ).toBe("POLYGON_API_KEY");
    expect(
      (screen.getByLabelText(/secret key 0/i) as HTMLInputElement).value,
    ).toBe("POLYGON_API_KEY");
    // value blanked — server does not return secret values
    expect(
      (screen.getByLabelText(/secret value 0/i) as HTMLInputElement).value,
    ).toBe("");
    expect(
      screen.getByRole("button", { name: /save changes/i }),
    ).toBeTruthy();
  });

  it("submit in edit mode calls updateConnector with the editing id", async () => {
    const onCreated = vi.fn();
    render(
      <AddConnectorForm
        onCancel={vi.fn()}
        onCreated={onCreated}
        editing={{
          id: "c-123",
          providerId: "polygon",
          displayName: "Polygon",
          source: "cli_mcp",
          category: "financial",
          launch: {
            modes: [
              {
                kind: "cli_mcp",
                argv: ["npx", "-y", "polygon-mcp"],
                env_keys: [],
              },
            ],
          },
          secretKeys: [],
        }}
      />,
    );

    fireEvent.change(screen.getByLabelText(/argv \(space-separated\)/i), {
      target: { value: "npx -y polygon-mcp@2" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(mocked.updateConnector).toHaveBeenCalled());
    expect(mocked.createConnector).not.toHaveBeenCalled();
    const [id, payload] = mocked.updateConnector.mock.calls[0];
    expect(id).toBe("c-123");
    expect(payload.launch.modes[0].argv).toEqual([
      "npx",
      "-y",
      "polygon-mcp@2",
    ]);
    expect(onCreated).toHaveBeenCalled();
  });

  it("edit mode omits secrets payload when no value entered (preserve existing)", async () => {
    render(
      <AddConnectorForm
        onCancel={vi.fn()}
        onCreated={vi.fn()}
        editing={{
          id: "c-123",
          providerId: "polygon",
          displayName: "Polygon",
          source: "cli_mcp",
          category: "financial",
          launch: {
            modes: [{ kind: "cli_mcp", argv: ["x"], env_keys: [] }],
          },
          secretKeys: ["POLYGON_API_KEY"],
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));
    await waitFor(() => expect(mocked.updateConnector).toHaveBeenCalled());
    const [, payload] = mocked.updateConnector.mock.calls[0];
    expect(payload.secrets).toBeUndefined();
  });

  it("edit mode includes secrets payload when user enters new values", async () => {
    render(
      <AddConnectorForm
        onCancel={vi.fn()}
        onCreated={vi.fn()}
        editing={{
          id: "c-123",
          providerId: "polygon",
          displayName: "Polygon",
          source: "cli_mcp",
          category: "financial",
          launch: {
            modes: [{ kind: "cli_mcp", argv: ["x"], env_keys: [] }],
          },
          secretKeys: ["POLYGON_API_KEY"],
        }}
      />,
    );

    fireEvent.change(screen.getByLabelText(/secret value 0/i), {
      target: { value: "new-key-value" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));
    await waitFor(() => expect(mocked.updateConnector).toHaveBeenCalled());
    const [, payload] = mocked.updateConnector.mock.calls[0];
    expect(payload.secrets).toEqual({ POLYGON_API_KEY: "new-key-value" });
  });

  it("cancel calls onCancel", () => {
    const onCancel = vi.fn();
    render(<AddConnectorForm onCancel={onCancel} onCreated={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalled();
  });
});
