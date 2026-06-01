import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SmartPasteMcpForm } from "../SmartPasteMcpForm";
import * as api from "../../../api/connectors";

vi.mock("../../../api/connectors", async () => {
  const actual = await vi.importActual<typeof api>("../../../api/connectors");
  return {
    ...actual,
    createConnector: vi.fn(),
  };
});

const mocked = api as unknown as {
  createConnector: ReturnType<typeof vi.fn>;
};

describe("SmartPasteMcpForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("parses a pasted URL, extracts the apikey as a secret, and submits", async () => {
    const created = vi.fn();
    const row: api.ConnectorRow = {
      id: "c1",
      provider_id: "alphavantage",
      display_name: "alphavantage",
      source: "remote_mcp",
      category: "financial",
      status: "validated",
      last_error: null,
      cached_tools_count: 3,
    };
    mocked.createConnector.mockResolvedValue(row);

    render(<SmartPasteMcpForm onCancel={() => {}} onCreated={created} />);

    fireEvent.change(screen.getByLabelText(/paste a url or command/i), {
      target: { value: "https://mcp.alphavantage.co/mcp?apikey=AV12345" },
    });

    // Detected secret value is pre-filled from the pasted key.
    expect(await screen.findByDisplayValue("AV12345")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /validate & add/i }));

    await waitFor(() => expect(mocked.createConnector).toHaveBeenCalledTimes(1));
    const payload = mocked.createConnector.mock.calls[0][0];
    expect(payload.source).toBe("remote_mcp");
    expect(payload.launch.modes[0]).toMatchObject({
      kind: "remote_mcp",
      url: "https://mcp.alphavantage.co/mcp?apikey={ALPHAVANTAGE_APIKEY}",
    });
    expect(payload.secrets).toEqual({ ALPHAVANTAGE_APIKEY: "AV12345" });
    expect(created).toHaveBeenCalledWith(row);
  });

  it("shows an error and does not submit when input is unclassifiable", () => {
    render(<SmartPasteMcpForm onCancel={() => {}} onCreated={() => {}} />);
    fireEvent.change(screen.getByLabelText(/paste a url or command/i), {
      target: { value: "https://" },
    });
    expect(screen.getByRole("button", { name: /validate & add/i })).toBeDisabled();
    expect(mocked.createConnector).not.toHaveBeenCalled();
  });
});
