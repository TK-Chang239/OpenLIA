import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { ReviewStep } from "./ReviewStep";

const json = (body: unknown) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

describe("ReviewStep", () => {
  it("polls /setup/review/{id} and renders readiness cards", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json({ review_id: "rev-1" }))
      .mockResolvedValueOnce(
        json({
          state: "complete",
          progress: 100,
          result: {
            summary: "1 of 1 ready.",
            departments: [
              {
                id: "secretary",
                state: "ready",
                note: null,
                basic: [{ type: "stock_quote", provider: "eodhd", confidence: 0.9 }],
                advanced: [],
                unmet: [],
              },
            ],
          },
          error: null,
        }),
      )
      .mockResolvedValueOnce(json({ redirect: "/", mode: "personal" }));

    render(<ReviewStep totalSteps={5} onBack={vi.fn()} />);
    await waitFor(() => screen.getByText(/1 of 1 ready/i));
    expect(screen.getByText(/secretary/i)).toBeInTheDocument();
  });

  it("Finish enabled when a department is blocked, with a warning banner listing it", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json({ review_id: "rev-1" }))
      .mockResolvedValueOnce(
        json({
          state: "complete",
          progress: 100,
          result: {
            summary: "0 of 1 ready.",
            departments: [
              {
                id: "equity_research",
                state: "blocked",
                note: null,
                basic: [],
                advanced: [],
                unmet: ["stock_quote"],
              },
            ],
          },
          error: null,
        }),
      );

    render(<ReviewStep totalSteps={5} onBack={vi.fn()} />);
    await waitFor(() => screen.getByText(/0 of 1 ready/i));
    expect(screen.getByRole("button", { name: /finish/i })).toBeEnabled();
    expect(screen.getByText(/1 department will be unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/equity research — needs stock_quote/i)).toBeInTheDocument();
  });
});
