import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import { CacheAdmin } from "./CacheAdmin";

describe("CacheAdmin", () => {
  beforeEach(() => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows loading state initially", () => {
    global.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch;
    render(<CacheAdmin />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders stats after fetch", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({ total_entries: 5, total_bytes: 2048 }),
    }) as unknown as typeof fetch;

    render(<CacheAdmin />);

    await waitFor(() => {
      expect(screen.getByText("5")).toBeInTheDocument();
    });
    expect(screen.getByText(/cached document/)).toBeInTheDocument();
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
  });

  it("clear button is disabled when ticker empty", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({ total_entries: 0, total_bytes: 0 }),
    }) as unknown as typeof fetch;

    render(<CacheAdmin />);

    await waitFor(() => {
      expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
    });

    const clearBtn = screen.getByRole("button", { name: /clear for ticker/i });
    expect(clearBtn).toBeDisabled();
  });

  it("clicking clear-all calls API after confirm", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);

    const calls: string[] = [];
    global.fetch = vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
      calls.push(`${opts?.method ?? "GET"} ${url}`);
      return Promise.resolve({
        ok: true,
        json: async () =>
          url.includes("/documents") ? { deleted: 3 } : { total_entries: 0, total_bytes: 0 },
      });
    }) as unknown as typeof fetch;

    render(<CacheAdmin />);

    await waitFor(() => {
      expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
    });

    const clearAllBtn = screen.getByRole("button", { name: /clear all cache/i });
    fireEvent.click(clearAllBtn);

    await waitFor(() => {
      expect(calls.some((c) => c.startsWith("DELETE"))).toBe(true);
    });

    const deleteCall = calls.find((c) => c.startsWith("DELETE"));
    expect(deleteCall).toContain("/api/cache/documents");
  });
});
