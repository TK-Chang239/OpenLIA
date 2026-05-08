import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TickerSelector } from "../TickerSelector";

describe("TickerSelector", () => {
  it("invokes onAdd via the add input + Enter key", () => {
    const onAdd = vi.fn();
    render(
      <TickerSelector
        tickers={[]}
        selected={null}
        onSelect={() => {}}
        onAdd={onAdd}
        onRemove={() => {}}
      />,
    );
    fireEvent.click(screen.getByTestId("ticker-add-button"));
    const input = screen.getByTestId("ticker-add-input");
    fireEvent.change(input, { target: { value: "msft" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onAdd).toHaveBeenCalledWith("MSFT");
  });

  it("invokes onRemove when × clicked", () => {
    const onRemove = vi.fn();
    render(
      <TickerSelector
        tickers={["AAPL"]}
        selected="AAPL"
        onSelect={() => {}}
        onAdd={() => {}}
        onRemove={onRemove}
      />,
    );
    fireEvent.click(screen.getByLabelText("Remove AAPL"));
    expect(onRemove).toHaveBeenCalledWith("AAPL");
  });

  it("renders Import-from-Portfolio when handler supplied", () => {
    const onImport = vi.fn();
    render(
      <TickerSelector
        tickers={[]}
        selected={null}
        onSelect={() => {}}
        onAdd={() => {}}
        onRemove={() => {}}
        onImportFromPortfolio={onImport}
      />,
    );
    fireEvent.click(screen.getByText(/Import from Portfolio/i));
    expect(onImport).toHaveBeenCalled();
  });

  it("shows the 21+ warning when too many tickers", () => {
    const tickers = Array.from({ length: 21 }, (_, i) => `T${i}`);
    render(
      <TickerSelector
        tickers={tickers}
        selected={null}
        onSelect={() => {}}
        onAdd={() => {}}
        onRemove={() => {}}
      />,
    );
    expect(screen.getByTestId("ticker-warning")).toBeInTheDocument();
  });
});
