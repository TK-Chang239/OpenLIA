import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ResolveRow } from "../ResolveRow";
import type { ResolveSaveResult } from "../../../api/runner_specs";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResp(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const NEED = {
  department_id: "macro_research",
  need_id: "stock_quote",
  description: "Latest closing price",
  shape: "float",
};

const ENDPOINTS = [
  { name: "quote", description: "Single-ticker quote" },
  { name: "search", description: "Search filings" },
];

describe("ResolveRow", () => {
  it("renders unresolved row with form expanded", () => {
    render(
      <ResolveRow
        need={NEED}
        status="unresolved"
        connectorId="c1"
        connectorCategory="financial"
        endpointOptions={ENDPOINTS}
        websearchAvailable={false}
        onSaved={() => {}}
      />,
    );
    expect(screen.getByText("stock_quote")).toBeInTheDocument();
    expect(screen.getByText("unresolved")).toBeInTheDocument();
    expect(screen.getByLabelText("Search endpoints")).toBeInTheDocument();
  });

  it("disables websearch mode when no web_search connector is available", () => {
    render(
      <ResolveRow
        need={NEED}
        status="unresolved"
        connectorId="c1"
        connectorCategory="financial"
        endpointOptions={ENDPOINTS}
        websearchAvailable={false}
        onSaved={() => {}}
      />,
    );
    const websearchRadio = screen.getByLabelText(/Websearch/);
    expect(websearchRadio).toBeDisabled();
  });

  it("save calls resolve endpoint and renders smoke failure panel on failure", async () => {
    const failureResp: ResolveSaveResult = {
      ok: false,
      warning: null,
      failure: {
        status: "auth",
        attempts: 1,
        error_class: "HTTPStatusError",
        error_message: "401 Unauthorized",
        response_excerpt: null,
      },
    };
    fetchMock.mockResolvedValueOnce(jsonResp(failureResp));
    const user = userEvent.setup();
    render(
      <ResolveRow
        need={NEED}
        status="unresolved"
        connectorId="c1"
        connectorCategory="financial"
        endpointOptions={ENDPOINTS}
        websearchAvailable={false}
        onSaved={() => {}}
      />,
    );
    await user.click(screen.getByText("quote"));
    await user.click(screen.getByText(/Save and smoke/));
    await waitFor(() => {
      expect(screen.getByText(/Authentication failed/)).toBeInTheDocument();
    });
    expect(screen.getByText(/401 Unauthorized/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0]!;
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.user_picked_endpoint).toBe("quote");
    expect(body.connector_id).toBe("c1");
  });

  it("warning modal offers proceed-with-override or cancel", async () => {
    const okResp: ResolveSaveResult = {
      ok: true,
      warning: "Endpoint returns intraday price",
      spec: {
        id: "s1",
        department_id: "macro_research",
        need_id: "stock_quote",
        connector_id: "c1",
        access_mode: "remote_mcp",
        spec: { tool_name: "quote" },
        canary_value: null,
        canary_at: null,
        resolution_mode: "manual_endpoint",
        manually_overridden: false,
        created_at: null,
        updated_at: null,
      },
    };
    fetchMock.mockResolvedValueOnce(jsonResp(okResp));
    const user = userEvent.setup();
    render(
      <ResolveRow
        need={NEED}
        status="unresolved"
        connectorId="c1"
        connectorCategory="financial"
        endpointOptions={ENDPOINTS}
        websearchAvailable={false}
        onSaved={() => {}}
      />,
    );
    await user.click(screen.getByText("quote"));
    await user.click(screen.getByText(/Save and smoke/));
    await waitFor(() => {
      expect(screen.getByText(/Endpoint returns intraday price/)).toBeInTheDocument();
    });
    // Warning modal must offer Proceed and Cancel.
    expect(screen.getByText(/Proceed anyway/)).toBeInTheDocument();
    expect(screen.getByText(/^Cancel$/)).toBeInTheDocument();

    // Proceed-anyway should re-call the endpoint with manually_overridden=true.
    const okOverride: ResolveSaveResult = { ...okResp, warning: null };
    fetchMock.mockResolvedValueOnce(jsonResp(okOverride));
    await user.click(screen.getByText(/Proceed anyway/));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
    const [, init] = fetchMock.mock.calls[1]!;
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.manually_overridden).toBe(true);
  });
});
