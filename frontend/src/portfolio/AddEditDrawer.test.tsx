import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api/portfolio";
import { AddEditDrawer } from "./AddEditDrawer";

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
    fireEvent.click(screen.getByTestId("drawer-save"));
    await new Promise((r) => setTimeout(r, 0));
    expect(api.createHolding).toHaveBeenCalled();
  });
});
