import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api/portfolio";
import { AddEditDrawer, __test } from "./AddEditDrawer";

const sample: api.PortfolioHolding = {
  id: "1",
  ticker: "AAPL",
  name: null,
  shares: "10",
  cost_basis: "150",
  currency: "USD",
  groups: [],
  notes_text: null,
  added_at: "",
  updated_at: "",
};

describe("AddEditDrawer", () => {
  beforeEach(() => {
    vi.spyOn(api, "createHolding").mockResolvedValue(sample);
    vi.spyOn(api, "updateHolding").mockResolvedValue(sample);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders nothing when closed", () => {
    const { container } = render(
      <AddEditDrawer
        open={false}
        mode="create"
        market="us" onClose={() => {}}
        onSaved={() => {}}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("disables ticker in edit mode", () => {
    render(
      <AddEditDrawer
        open
        mode="edit"
        initial={sample}
        market="us" onClose={() => {}}
        onSaved={() => {}}
      />,
    );
    expect(screen.getByTestId("drawer-ticker")).toBeDisabled();
  });

  it("calls createHolding on save in create mode", async () => {
    const onSaved = vi.fn();
    render(
      <AddEditDrawer
        open
        mode="create"
        market="us" onClose={() => {}}
        onSaved={onSaved}
      />,
    );
    fireEvent.change(screen.getByTestId("drawer-ticker"), {
      target: { value: "MSFT" },
    });
    fireEvent.change(screen.getByTestId("drawer-shares"), {
      target: { value: "5" },
    });
    fireEvent.click(screen.getByTestId("drawer-save"));
    await new Promise((r) => setTimeout(r, 0));
    expect(api.createHolding).toHaveBeenCalled();
  });
});

describe("AddEditDrawer helpers", () => {
  const { parseDecimal, formatDecimal, computeBlend } = __test;

  describe("parseDecimal", () => {
    it("returns null for empty / whitespace", () => {
      expect(parseDecimal("")).toBeNull();
      expect(parseDecimal("   ")).toBeNull();
    });

    it("returns null for non-numeric", () => {
      expect(parseDecimal("abc")).toBeNull();
    });

    it("parses positive decimals", () => {
      expect(parseDecimal("128.40")).toBe(128.4);
      expect(parseDecimal("0.5")).toBe(0.5);
    });

    it("returns null for negative or zero", () => {
      expect(parseDecimal("-1")).toBeNull();
      expect(parseDecimal("0")).toBeNull();
    });
  });

  describe("formatDecimal", () => {
    it("trims trailing zeros up to 4 dp", () => {
      expect(formatDecimal(110)).toBe("110");
      expect(formatDecimal(129.5454545)).toBe("129.5455");
      expect(formatDecimal(130.4)).toBe("130.4");
      expect(formatDecimal(130.4000)).toBe("130.4");
    });

    it("formats whole numbers without decimals", () => {
      expect(formatDecimal(0)).toBe("0");
    });
  });

  describe("computeBlend (Buy)", () => {
    it("blends weighted avg cost basis", () => {
      const { newShares, newCostBasis } = computeBlend({
        action: "buy",
        currentShares: 100,
        currentCostBasis: 128,
        qty: 10,
        price: 145,
      });
      expect(newShares).toBe(110);
      expect(newCostBasis).toBeCloseTo((100 * 128 + 10 * 145) / 110, 6);
    });

    it("sets cost basis = price when current cost basis is null", () => {
      const { newShares, newCostBasis } = computeBlend({
        action: "buy",
        currentShares: 100,
        currentCostBasis: null,
        qty: 10,
        price: 145,
      });
      expect(newShares).toBe(110);
      expect(newCostBasis).toBe(145);
    });

    it("sets shares=qty, cost=price when current shares is null", () => {
      const { newShares, newCostBasis } = computeBlend({
        action: "buy",
        currentShares: null,
        currentCostBasis: null,
        qty: 10,
        price: 145,
      });
      expect(newShares).toBe(10);
      expect(newCostBasis).toBe(145);
    });

    it("sets shares=qty, cost=price when current shares is 0", () => {
      const { newShares, newCostBasis } = computeBlend({
        action: "buy",
        currentShares: 0,
        currentCostBasis: 99,
        qty: 10,
        price: 145,
      });
      expect(newShares).toBe(10);
      expect(newCostBasis).toBe(145);
    });
  });

  describe("computeBlend (Sell)", () => {
    it("decrements shares and leaves cost basis unchanged", () => {
      const { newShares, newCostBasis } = computeBlend({
        action: "sell",
        currentShares: 100,
        currentCostBasis: 128,
        qty: 25,
        price: 135,
      });
      expect(newShares).toBe(75);
      expect(newCostBasis).toBe(128);
    });

    it("keeps cost basis null when it was null", () => {
      const { newShares, newCostBasis } = computeBlend({
        action: "sell",
        currentShares: 100,
        currentCostBasis: null,
        qty: 25,
        price: 135,
      });
      expect(newShares).toBe(75);
      expect(newCostBasis).toBeNull();
    });
  });
});
