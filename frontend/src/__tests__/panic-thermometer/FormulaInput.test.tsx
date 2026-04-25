import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FormulaInput } from "../../components/panic-thermometer/FormulaInput";

const parseFormulaMock = vi.fn();

vi.mock("../../api/panic-thermometer", () => ({
  parseFormula: (...args: unknown[]) => parseFormulaMock(...args),
}));

describe("FormulaInput", () => {
  it("debounces parse and shows identifier chips on success", async () => {
    parseFormulaMock.mockResolvedValueOnce({ ok: true, identifiers: ["price", "x"] });
    const onChange = vi.fn();
    render(<FormulaInput panel="oil" value="price > x" onChange={onChange} />);
    await waitFor(
      () => {
        expect(screen.getByTestId("formula-identifiers")).toBeInTheDocument();
      },
      { timeout: 1000 },
    );
    expect(parseFormulaMock).toHaveBeenCalled();
  });

  it("shows error message on parse failure", async () => {
    parseFormulaMock.mockResolvedValueOnce({
      ok: false,
      errors: [{ type: "parse", message: "syntax error" }],
    });
    render(<FormulaInput panel="oil" value="bad >>>" onChange={() => {}} />);
    await waitFor(
      () => {
        expect(screen.getByTestId("formula-error")).toHaveTextContent(/syntax error/);
      },
      { timeout: 1000 },
    );
  });

  it("calls onChange when user types", () => {
    const onChange = vi.fn();
    render(<FormulaInput panel="oil" value="" onChange={onChange} />);
    fireEvent.change(screen.getByTestId("formula-input"), {
      target: { value: "price > 10" },
    });
    expect(onChange).toHaveBeenCalledWith("price > 10");
  });
});
