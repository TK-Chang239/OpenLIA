import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AddTickerPopover } from "../AddTickerPopover";

describe("AddTickerPopover", () => {
  it("submits uppercased ticker on Add click", async () => {
    const onAdd = vi.fn().mockResolvedValue(undefined);
    render(<AddTickerPopover onAdd={onAdd} />);
    fireEvent.click(screen.getByRole("button", { name: /add ticker/i }));
    const input = await screen.findByPlaceholderText(/ticker symbol/i);
    fireEvent.change(input, { target: { value: "aapl" } });
    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));
    expect(onAdd).toHaveBeenCalledWith("AAPL");
  });

  it("shows error on 409", async () => {
    const onAdd = vi
      .fn()
      .mockRejectedValue(Object.assign(new Error("x"), { status: 409 }));
    render(<AddTickerPopover onAdd={onAdd} />);
    fireEvent.click(screen.getByRole("button", { name: /add ticker/i }));
    const input = await screen.findByPlaceholderText(/ticker symbol/i);
    fireEvent.change(input, { target: { value: "AAPL" } });
    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));
    expect(await screen.findByText(/already watching/i)).toBeInTheDocument();
  });
});
