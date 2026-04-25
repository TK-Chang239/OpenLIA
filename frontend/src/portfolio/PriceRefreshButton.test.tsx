import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PriceRefreshButton } from "./PriceRefreshButton";

describe("PriceRefreshButton", () => {
  it("calls onSuccess on success", async () => {
    const onSuccess = vi.fn();
    render(
      <PriceRefreshButton
        onRefresh={async () => {}}
        onSuccess={onSuccess}
      />,
    );
    fireEvent.click(screen.getByTestId("price-refresh-btn"));
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });

  it("surfaces 429 rate-limit message", async () => {
    render(
      <PriceRefreshButton
        onRefresh={async () => {
          const err = new Error("Try again in 30 seconds") as Error & {
            retryAfter?: number;
            status?: number;
          };
          err.status = 429;
          err.retryAfter = 30;
          throw err;
        }}
      />,
    );
    fireEvent.click(screen.getByTestId("price-refresh-btn"));
    await waitFor(() => screen.getByTestId("price-refresh-error"));
    expect(screen.getByTestId("price-refresh-error")).toHaveTextContent(
      "Try again in 30 seconds",
    );
  });
});
