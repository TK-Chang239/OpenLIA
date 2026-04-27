import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReviewStep } from "./ReviewStep";
import * as connectorsApi from "../../api/connectors";

vi.mock("../../api/connectors", async () => {
  const actual = await vi.importActual<typeof connectorsApi>(
    "../../api/connectors",
  );
  return {
    ...actual,
    scopeAll: vi.fn(),
    getReview: vi.fn(),
  };
});

const mockedScopeAll = vi.mocked(connectorsApi.scopeAll);
const mockedGetReview = vi.mocked(connectorsApi.getReview);

const READY_AND_NOT_READY = {
  departments: [
    {
      department_id: "secretary",
      ready: true,
      categories: [
        {
          category: "financial" as const,
          required: true,
          status: "ok" as const,
          tool_count: 5,
          providers: ["eodhd"],
        },
        {
          category: "news" as const,
          required: true,
          status: "ok" as const,
          tool_count: 2,
          providers: ["newsapi"],
        },
        {
          category: "social" as const,
          required: false,
          status: "basic" as const,
          tool_count: 0,
          providers: [],
        },
        {
          category: "web_search" as const,
          required: false,
          status: "enhanced" as const,
          tool_count: 3,
          providers: ["serper"],
        },
      ],
    },
    {
      department_id: "equity_research",
      ready: false,
      categories: [
        {
          category: "financial" as const,
          required: true,
          status: "missing" as const,
          tool_count: 0,
          providers: [],
        },
        {
          category: "news" as const,
          required: true,
          status: "ok" as const,
          tool_count: 2,
          providers: ["newsapi"],
        },
      ],
    },
  ],
};

beforeEach(() => {
  mockedScopeAll.mockReset();
  mockedGetReview.mockReset();
});

describe("ReviewStep", () => {
  it("calls scopeAll once on mount and renders Ready and Not Ready departments", async () => {
    mockedScopeAll.mockResolvedValue({ scoped: 0, per_connector: [] });
    mockedGetReview.mockResolvedValue(READY_AND_NOT_READY);

    render(<ReviewStep totalSteps={5} onBack={vi.fn()} />);

    await waitFor(() => screen.getByText(/secretary/i));
    expect(mockedScopeAll).toHaveBeenCalledTimes(1);

    expect(screen.getByLabelText(/secretary Ready/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/equity_research Not Ready/i)).toBeInTheDocument();
    expect(screen.getByText(/✓ financial: 5 tools — eodhd/)).toBeInTheDocument();
    expect(
      screen.getByText(/✗ financial: 0 tools — add a financial connector/),
    ).toBeInTheDocument();
    expect(screen.getByText(/social: basic — no connector/)).toBeInTheDocument();
    expect(screen.getByText(/web search: enhanced — 3 tools, serper/)).toBeInTheDocument();
  });

  it("places Not Ready departments before Ready ones", async () => {
    mockedScopeAll.mockResolvedValue({ scoped: 0, per_connector: [] });
    mockedGetReview.mockResolvedValue(READY_AND_NOT_READY);

    render(<ReviewStep totalSteps={5} onBack={vi.fn()} />);

    await waitFor(() => screen.getByText(/secretary/i));
    const headings = screen.getAllByRole("heading", { level: 4 });
    expect(headings[0]).toHaveTextContent(/equity research/i);
    expect(headings[1]).toHaveTextContent(/secretary/i);
  });

  it("Re-scope all triggers scopeAll then getReview in order", async () => {
    const callOrder: string[] = [];
    mockedScopeAll.mockImplementation(async () => {
      callOrder.push("scopeAll");
      return { scoped: 0, per_connector: [] };
    });
    mockedGetReview.mockImplementation(async () => {
      callOrder.push("getReview");
      return READY_AND_NOT_READY;
    });

    render(<ReviewStep totalSteps={5} onBack={vi.fn()} />);
    await waitFor(() => screen.getByText(/secretary/i));

    expect(callOrder).toEqual(["scopeAll", "getReview"]);

    const button = screen.getByRole("button", { name: /re-scope all/i });
    await userEvent.click(button);

    await waitFor(() => expect(mockedScopeAll).toHaveBeenCalledTimes(2));
    expect(callOrder).toEqual([
      "scopeAll",
      "getReview",
      "scopeAll",
      "getReview",
    ]);
    expect(mockedGetReview).toHaveBeenCalledTimes(2);
  });

  it("surfaces an error message when scopeAll throws", async () => {
    mockedScopeAll.mockRejectedValue(new Error("scope boom"));

    render(<ReviewStep totalSteps={5} onBack={vi.fn()} />);

    await waitFor(() => screen.getByRole("alert"));
    expect(screen.getByRole("alert")).toHaveTextContent(/scope boom/i);
    expect(mockedGetReview).not.toHaveBeenCalled();
  });

  it("surfaces an error message when getReview throws", async () => {
    mockedScopeAll.mockResolvedValue({ scoped: 0, per_connector: [] });
    mockedGetReview.mockRejectedValue(new Error("review boom"));

    render(<ReviewStep totalSteps={5} onBack={vi.fn()} />);

    await waitFor(() => screen.getByRole("alert"));
    expect(screen.getByRole("alert")).toHaveTextContent(/review boom/i);
  });
});
