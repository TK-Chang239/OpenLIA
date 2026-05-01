import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DeptResolvePanel } from "../DeptResolvePanel";

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

function connectorListResp(ids: string[]): Response {
  return jsonResp(ids.map((id) => ({ id })));
}

describe("DeptResolvePanel", () => {
  it("loads cached proposals on mount", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResp([
        {
          department_id: "macro_research",
          need_id: "real_time_quote",
          proposed_spec: { tool_name: "get_quote" },
          canary_value: { price: 1 },
          canary_ok: true,
          shape_match: true,
          error: null,
          connector_id: "c1",
          unsatisfiable: false,
        },
      ]),
    );

    render(
      <DeptResolvePanel departmentId="macro_research" label="Macro Research" />,
    );

    await waitFor(() => {
      expect(
        screen.getByText("real_time_quote", { exact: false }),
      ).toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/departments/macro_research/proposed-specs",
      expect.anything(),
    );
  });

  it("clicking Resolve posts to the resolve endpoint and shows results", async () => {
    fetchMock.mockImplementation((url: string) => {
      const u = String(url);
      if (u.endsWith("/proposed-specs")) return Promise.resolve(jsonResp([]));
      if (u.endsWith("/proposed-specs/resolve")) {
        return Promise.resolve(
          jsonResp([
            {
              department_id: "macro_research",
              need_id: "geopolitical_news",
              proposed_spec: { tool_name: "get_news" },
              canary_value: null,
              canary_ok: false,
              shape_match: false,
              error: null,
              connector_id: "c2",
              unsatisfiable: false,
            },
          ]),
        );
      }
      if (u.endsWith("/proposed-specs/events")) return Promise.resolve(jsonResp([]));
      if (u === "/api/connectors") return Promise.resolve(connectorListResp(["c2"]));
      throw new Error(`unmocked fetch: ${u}`);
    });

    render(
      <DeptResolvePanel departmentId="macro_research" label="Macro Research" />,
    );

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /resolve macro research/i }),
      ).toBeInTheDocument();
    });

    await userEvent.click(
      screen.getByRole("button", { name: /resolve macro research/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/geopolitical_news/)).toBeInTheDocument();
    });
    const resolveCall = fetchMock.mock.calls.find(
      (c) =>
        c[0] === "/api/departments/macro_research/proposed-specs/resolve",
    );
    expect(resolveCall).toBeTruthy();
    expect((resolveCall![1] as RequestInit).method).toBe("POST");
  });

  it("clicking Approve posts need_id to the dept approve endpoint", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResp([
        {
          department_id: "macro_research",
          need_id: "real_time_quote",
          proposed_spec: { tool_name: "get_quote" },
          canary_value: { price: 1 },
          canary_ok: true,
          shape_match: true,
          error: null,
          connector_id: "c1",
          unsatisfiable: false,
        },
      ]),
    );
    fetchMock.mockResolvedValueOnce(
      jsonResp({
        id: "rcs1",
        department_id: "macro_research",
        need_id: "real_time_quote",
        connector_id: "c1",
        access_mode: "cli_mcp",
      }),
    );
    // dept-health refresh after approve
    fetchMock.mockResolvedValue(jsonResp([]));

    render(
      <DeptResolvePanel departmentId="macro_research" label="Macro Research" />,
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /^approve$/i }),
      ).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("button", { name: /^approve$/i }));

    await waitFor(() => {
      const approveCall = fetchMock.mock.calls.find(
        (c) =>
          c[0] === "/api/departments/macro_research/proposed-specs/approve",
      );
      expect(approveCall).toBeTruthy();
      const init = approveCall![1] as RequestInit;
      expect(init.method).toBe("POST");
      expect(init.body).toBe(
        JSON.stringify({ need_id: "real_time_quote", connector_id: "c1" }),
      );
    });
  });

  it("renders streamed tool-call events while resolving", async () => {
    // Initial GET (cached proposals) — none yet.
    fetchMock.mockResolvedValueOnce(jsonResp([]));
    // The Resolve POST takes time; resolve(...) fires the resolve, but the
    // panel polls events meanwhile.
    let resolveResolve: ((v: Response) => void) | null = null;
    const resolvePending = new Promise<Response>((res) => {
      resolveResolve = res;
    });
    fetchMock.mockImplementationOnce((url: string) => {
      // POST .../resolve
      expect(String(url)).toContain("/proposed-specs/resolve");
      return resolvePending;
    });
    // Subsequent calls: events poll, then listConnectors after resolve.
    fetchMock.mockResolvedValue(
      jsonResp([
        {
          type: "tool_call",
          need_id: "quote",
          connector_id: "c1",
          name: "read_file",
          arguments: { path: "app/tools/get_macro_indicator.py" },
        },
      ]),
    );

    render(
      <DeptResolvePanel departmentId="macro_research" label="Macro Research" />,
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /resolve macro research/i }),
      ).toBeInTheDocument(),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /resolve macro research/i }),
    );

    await waitFor(() =>
      expect(
        screen.getByText(/get_macro_indicator\.py/),
      ).toBeInTheDocument(),
    );

    // Let the resolve POST finish so React effects unwind cleanly.
    resolveResolve!(jsonResp([]));
  });

  it("clicking per-need Re-resolve calls the per-need endpoint", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResp([
        {
          department_id: "macro_research",
          need_id: "real_time_quote",
          proposed_spec: { tool_name: "old_tool" },
          canary_value: null,
          canary_ok: false,
          shape_match: false,
          error: null,
          connector_id: "c1",
          unsatisfiable: false,
        },
      ]),
    );
    fetchMock.mockResolvedValueOnce(
      jsonResp([
        {
          department_id: "macro_research",
          need_id: "real_time_quote",
          proposed_spec: { tool_name: "fresh_tool" },
          canary_value: null,
          canary_ok: false,
          shape_match: false,
          error: null,
          connector_id: "c1",
          unsatisfiable: false,
        },
      ]),
    );

    render(
      <DeptResolvePanel departmentId="macro_research" label="Macro Research" />,
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Re-resolve" }),
      ).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("button", { name: "Re-resolve" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenLastCalledWith(
        "/api/departments/macro_research/proposed-specs/real_time_quote/resolve",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    await waitFor(() =>
      expect(screen.getByText(/fresh_tool/)).toBeInTheDocument(),
    );
  });

  it("renders all candidates for a need with their constants", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResp([
        {
          department_id: "macro_research",
          need_id: "debt_gdp",
          proposed_spec: {
            tool_name: "get_macro_indicator",
            constants: { indicator: "debt_percent_gdp" },
          },
          canary_value: null,
          canary_ok: false,
          shape_match: false,
          error: null,
          connector_id: "c1",
          unsatisfiable: false,
        },
        {
          department_id: "macro_research",
          need_id: "debt_gdp",
          proposed_spec: {
            method: "APIClient.get_macro_indicators_data",
            constants: { country: "US" },
          },
          canary_value: null,
          canary_ok: false,
          shape_match: false,
          error: null,
          connector_id: "c2",
          unsatisfiable: false,
        },
      ]),
    );

    render(
      <DeptResolvePanel departmentId="macro_research" label="Macro Research" />,
    );

    await waitFor(() => {
      expect(screen.getAllByText(/get_macro_indicator/).length).toBeGreaterThan(0);
    });
    expect(
      screen.getAllByText("indicator=debt_percent_gdp").length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText(/APIClient/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("country=US").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/2 candidates/i).length).toBeGreaterThan(0);
  });

  it("Approve all approves the first usable candidate of every unapproved need", async () => {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      const u = String(url);
      if (u === "/api/departments/macro_research/proposed-specs") {
        return Promise.resolve(
          jsonResp([
            {
              department_id: "macro_research",
              need_id: "n1",
              proposed_spec: { tool_name: "t1" },
              canary_value: null,
              canary_ok: true,
              shape_match: true,
              error: null,
              connector_id: "c1",
              unsatisfiable: false,
            },
            {
              department_id: "macro_research",
              need_id: "n1",
              proposed_spec: { tool_name: "t1b" },
              canary_value: null,
              canary_ok: false,
              shape_match: false,
              error: null,
              connector_id: "c2",
              unsatisfiable: false,
            },
            {
              department_id: "macro_research",
              need_id: "n2",
              proposed_spec: { tool_name: "t2" },
              canary_value: null,
              canary_ok: true,
              shape_match: true,
              error: null,
              connector_id: "c3",
              unsatisfiable: false,
            },
          ]),
        );
      }
      if (u.endsWith("/proposed-specs/approve") && init?.method === "POST") {
        return Promise.resolve(
          jsonResp({
            id: "x",
            department_id: "macro_research",
            need_id: "n",
            connector_id: "c",
            access_mode: "cli_mcp",
          }),
        );
      }
      if (u === "/api/dept-health") return Promise.resolve(jsonResp([]));
      return Promise.resolve(jsonResp([]));
    });

    render(
      <DeptResolvePanel departmentId="macro_research" label="Macro Research" />,
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /approve all \(2\)/i }),
      ).toBeInTheDocument(),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /approve all \(2\)/i }),
    );

    await waitFor(() => {
      const approveCalls = fetchMock.mock.calls.filter(
        (c) =>
          c[0] === "/api/departments/macro_research/proposed-specs/approve",
      );
      expect(approveCalls.length).toBe(2);
      const bodies = approveCalls
        .map((c) => (c[1] as RequestInit).body as string)
        .map((b) => JSON.parse(b));
      expect(bodies).toEqual([
        { need_id: "n1", connector_id: "c1" },
        { need_id: "n2", connector_id: "c3" },
      ]);
    });
  });

  it("does not show Approve for unsatisfiable proposals", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResp([
        {
          department_id: "macro_research",
          need_id: "exotic",
          proposed_spec: {},
          canary_value: null,
          canary_ok: false,
          shape_match: false,
          error: null,
          connector_id: null,
          unsatisfiable: true,
        },
      ]),
    );

    render(
      <DeptResolvePanel departmentId="macro_research" label="Macro Research" />,
    );

    await waitFor(() =>
      expect(screen.getByText(/exotic/)).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: /^approve$/i }),
    ).not.toBeInTheDocument();
  });

  it("surfaces a change-detection hint when connectors changed since last resolve", async () => {
    sessionStorage.setItem(
      "openlia.dept-resolve-snapshot:macro_research",
      JSON.stringify(["c1", "c2"]),
    );
    fetchMock.mockResolvedValueOnce(
      jsonResp([
        {
          department_id: "macro_research",
          need_id: "real_time_quote",
          proposed_spec: { tool_name: "get_quote" },
          canary_value: { price: 1 },
          canary_ok: true,
          shape_match: true,
          error: null,
          connector_id: "c1",
          unsatisfiable: false,
        },
      ]),
    );
    // listConnectors returns a different set (added c3).
    fetchMock.mockResolvedValueOnce(connectorListResp(["c1", "c2", "c3"]));

    render(
      <DeptResolvePanel departmentId="macro_research" label="Macro Research" />,
    );

    await waitFor(() => {
      expect(
        screen.getByText(/connectors changed since last resolve/i),
      ).toBeInTheDocument();
    });
    sessionStorage.clear();
  });

  it("does not show hint when proposals match current connectors", async () => {
    sessionStorage.setItem(
      "openlia.dept-resolve-snapshot:macro_research",
      JSON.stringify(["c1"]),
    );
    fetchMock.mockResolvedValueOnce(
      jsonResp([
        {
          department_id: "macro_research",
          need_id: "real_time_quote",
          proposed_spec: { tool_name: "get_quote" },
          canary_value: { price: 1 },
          canary_ok: true,
          shape_match: true,
          error: null,
          connector_id: "c1",
          unsatisfiable: false,
        },
      ]),
    );
    fetchMock.mockResolvedValueOnce(connectorListResp(["c1"]));

    render(
      <DeptResolvePanel departmentId="macro_research" label="Macro Research" />,
    );

    await waitFor(() =>
      expect(screen.getByText(/real_time_quote/)).toBeInTheDocument(),
    );
    expect(
      screen.queryByText(/connectors changed since last resolve/i),
    ).not.toBeInTheDocument();
    sessionStorage.clear();
  });

  it("renders unsatisfiable proposals as a clear warning", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResp([
        {
          department_id: "macro_research",
          need_id: "pmi_index",
          proposed_spec: {},
          canary_value: null,
          canary_ok: false,
          shape_match: false,
          error: null,
          connector_id: null,
          unsatisfiable: true,
        },
      ]),
    );

    render(
      <DeptResolvePanel departmentId="macro_research" label="Macro Research" />,
    );

    await waitFor(() => {
      expect(screen.getByText(/pmi_index/)).toBeInTheDocument();
    });
    expect(screen.getByText(/no.*connector/i)).toBeInTheDocument();
  });
});
