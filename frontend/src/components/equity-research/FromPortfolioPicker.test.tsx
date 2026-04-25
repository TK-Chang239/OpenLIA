import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { FromPortfolioPicker } from "./FromPortfolioPicker";

let originalFetch: typeof fetch | undefined;

beforeEach(() => {
  originalFetch = globalThis.fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch as typeof fetch;
  vi.clearAllMocks();
});

describe("FromPortfolioPicker", () => {
  it("loads holdings on open and fires onSelect when a row is clicked", async () => {
    const onSelect = vi.fn();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [
        { ticker: "GOOG", name: "Alphabet" },
        { ticker: "AMZN", name: "Amazon" },
      ],
    } as unknown as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    render(<FromPortfolioPicker onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /from portfolio/i }));

    await waitFor(() => expect(screen.getByText("GOOG")).toBeInTheDocument());
    fireEvent.click(screen.getByText("GOOG"));
    expect(onSelect).toHaveBeenCalledWith("GOOG");
  });

  it("renders a fallback when the portfolio fetch fails", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("nope"));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    render(<FromPortfolioPicker onSelect={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /from portfolio/i }));
    await waitFor(() =>
      expect(screen.getByText(/portfolio unavailable/i)).toBeInTheDocument(),
    );
  });
});
