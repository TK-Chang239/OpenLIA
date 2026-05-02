import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CatalogGrid } from "../CatalogGrid";
import type { BuiltinTemplate } from "../../../api/connectors";

const TEMPLATES: BuiltinTemplate[] = [
  {
    template_id: "firecrawl",
    display_name: "Firecrawl",
    category: "web_search",
    api_key_env_var: "FIRECRAWL_API_KEY",
    covered_need_ids: [
      "usd_fx_reserve_share",
      "cb_gold_purchases",
      "foreign_treasury_holdings",
    ],
  },
  {
    template_id: "x",
    display_name: "X",
    category: "social",
    api_key_env_var: "X_API_KEY",
    covered_need_ids: [],
  },
];

describe("CatalogGrid", () => {
  it("renders a card per template", () => {
    render(<CatalogGrid templates={TEMPLATES} onSelect={() => {}} />);
    expect(screen.getByText("Firecrawl")).toBeInTheDocument();
    expect(screen.getByText("X")).toBeInTheDocument();
  });

  it("calls onSelect with the template when a card is clicked", () => {
    const onSelect = vi.fn();
    render(<CatalogGrid templates={TEMPLATES} onSelect={onSelect} />);
    fireEvent.click(screen.getByText("Firecrawl"));
    expect(onSelect).toHaveBeenCalledWith(TEMPLATES[0]);
  });

  it("renders the category badge per card", () => {
    render(<CatalogGrid templates={TEMPLATES} onSelect={() => {}} />);
    expect(screen.getByText(/web_search/i)).toBeInTheDocument();
    expect(screen.getByText(/social/i)).toBeInTheDocument();
  });
});
