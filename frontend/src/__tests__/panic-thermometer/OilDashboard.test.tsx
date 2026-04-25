import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OilDashboard } from "../../components/panic-thermometer/OilDashboard";

describe("OilDashboard", () => {
  it("renders threshold and latest price", () => {
    render(
      <OilDashboard
        result={{
          panel_id: "oil",
          status: "amber",
          label: "above",
          resolved_values: { price: 92.5, price_threshold: 85 },
          derived_scalars: {},
          extras: {},
          warnings: [],
        }}
      />,
    );
    expect(screen.getByTestId("oil-dashboard")).toHaveTextContent("$85.00");
    expect(screen.getByTestId("oil-dashboard")).toHaveTextContent("$92.50");
  });

  it("renders fallback when no data", () => {
    render(<OilDashboard result={undefined} />);
    expect(screen.getByText(/No price data/i)).toBeInTheDocument();
  });
});
