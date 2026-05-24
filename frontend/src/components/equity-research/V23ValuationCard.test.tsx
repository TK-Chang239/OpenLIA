import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  V23BundleFact,
  V23RunPayload,
} from "../../api/equity-research-v2-3";

import { V23ValuationCard } from "./V23ValuationCard";

function payloadWith(facts: Record<string, V23BundleFact>): V23RunPayload {
  return {
    run_id: "r1",
    tickers: ["NVDA"],
    report_type: "initiation",
    language: "en",
    thesis: {
      language: "en",
      central_argument: "",
      key_takeaways: [],
      valuation_stance: "",
      canonical_figures: [],
    },
    sections: [],
    section_bodies: {},
    footnotes: [],
    charts: [],
    figure_labels: {},
    bundle_facts: facts,
  };
}

function fact(
  id: string,
  value: V23BundleFact["value"],
  unit: string | null = null,
): V23BundleFact {
  return { id, label: id, value, unit, ticker: "NVDA" };
}

describe("V23ValuationCard", () => {
  it("renders nothing when no valuation facts are present", () => {
    const { container } = render(<V23ValuationCard payload={payloadWith({})} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("formats DCF per-share value with the $ prefix", () => {
    render(
      <V23ValuationCard
        payload={payloadWith({
          dcf_fair_value: fact("dcf_fair_value", 1420, "USD"),
        })}
      />,
    );
    const row = screen.getByTestId("er-v2-3-valuation-row-dcf_fair_value");
    expect(row).toHaveTextContent("$1,420");
    expect(row).toHaveTextContent(/Fair value per share/i);
  });

  it("renders enterprise value in millions notation", () => {
    render(
      <V23ValuationCard
        payload={payloadWith({
          dcf_enterprise_value: fact("dcf_enterprise_value", 3450000, "USD_millions"),
        })}
      />,
    );
    expect(
      screen.getByTestId("er-v2-3-valuation-row-dcf_enterprise_value"),
    ).toHaveTextContent("$3,450,000M");
  });

  it("expands a comps_implied_<multiple> row per multiple with friendly labels", () => {
    render(
      <V23ValuationCard
        payload={payloadWith({
          comps_implied_pe: fact("comps_implied_pe", 1530, "USD"),
          comps_implied_evebitda: fact("comps_implied_evebitda", 1610, "USD"),
        })}
      />,
    );
    expect(
      screen.getByTestId("er-v2-3-valuation-row-comps_implied_pe"),
    ).toHaveTextContent(/P\/E/);
    expect(
      screen.getByTestId("er-v2-3-valuation-row-comps_implied_evebitda"),
    ).toHaveTextContent(/EV\/EBITDA/);
  });

  it("collapses a sensitivity grid into a single row with point count", () => {
    render(
      <V23ValuationCard
        payload={payloadWith({
          sensitivity_grid: fact(
            "sensitivity_grid",
            [
              { period: "wacc=8,g=2", value: 1100 },
              { period: "wacc=10,g=2", value: 1300 },
              { period: "wacc=10,g=3", value: 1450 },
            ],
            null,
          ),
        })}
      />,
    );
    expect(
      screen.getByTestId("er-v2-3-valuation-row-sensitivity_grid"),
    ).toHaveTextContent(/3 grid points/);
  });
});
