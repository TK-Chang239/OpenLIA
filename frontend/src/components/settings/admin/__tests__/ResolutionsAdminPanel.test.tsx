import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ResolutionsAdminPanel } from "../ResolutionsAdminPanel";

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

describe("ResolutionsAdminPanel", () => {
  it("renders all resolved specs and offers a history button per row", async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.includes("/runner-specs") && !url.includes("/history")) {
        return Promise.resolve(
          jsonResp([
            {
              id: "s1",
              department_id: "macro_research",
              need_id: "stock_quote",
              connector_id: "c1",
              access_mode: "remote_mcp",
              spec: { tool_name: "quote" },
              canary_value: null,
              canary_at: null,
              resolution_mode: "manual_endpoint",
              created_at: null,
              updated_at: null,
            },
          ]),
        );
      }
      if (url.includes("/connectors")) {
        return Promise.resolve(
          jsonResp([
            {
              id: "c1",
              provider_id: "fmp",
              display_name: "FMP",
              source: "remote_mcp",
              category: "financial",
              status: "validated",
              last_error: null,
              cached_tools_count: 5,
            },
          ]),
        );
      }
      return Promise.resolve(jsonResp([]));
    });
    render(<ResolutionsAdminPanel />);
    await waitFor(() => {
      expect(screen.getByText("stock_quote")).toBeInTheDocument();
    });
    expect(screen.getByText(/^History$/)).toBeInTheDocument();
  });
});
