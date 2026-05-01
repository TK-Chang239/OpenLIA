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
    fetchMock.mockResolvedValueOnce(jsonResp([])); // initial GET
    fetchMock.mockResolvedValueOnce(
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
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/departments/macro_research/proposed-specs/resolve",
      expect.objectContaining({ method: "POST" }),
    );
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
