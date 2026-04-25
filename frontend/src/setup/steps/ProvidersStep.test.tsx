import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { ProvidersStep } from "./ProvidersStep";

describe("ProvidersStep", () => {
  it("renders 4 category tabs and list of providers", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ providers: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    render(<ProvidersStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />);
    await waitFor(() => expect(screen.getByRole("tablist")).toBeInTheDocument());
    expect(screen.getByRole("tab", { name: /financial/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /news/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /social/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /web search/i })).toBeInTheDocument();
  });

  it("gate: Next disabled until ≥1 financial AND ≥1 news provider green", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          providers: [
            { id: "p1", category: "financial", mode: "builtin", provider: "eodhd", priority: 0, status: "ok" },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    render(<ProvidersStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />);
    await waitFor(() => screen.getByRole("tablist"));
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  it("Next disabled when no green News provider (financial green only)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          providers: [
            { id: "p1", category: "financial", mode: "builtin", provider: "eodhd", priority: 0, status: "ok" },
            { id: "p2", category: "news", mode: "builtin", provider: "newsapi_org", priority: 0, status: "error" },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    render(<ProvidersStep totalSteps={5} onBack={vi.fn()} onSaved={vi.fn()} />);
    await waitFor(() => screen.getByRole("tablist"));
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });
});
