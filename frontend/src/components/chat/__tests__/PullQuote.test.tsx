import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PullQuote, parsePullQuote } from "../PullQuote";

describe("parsePullQuote", () => {
  it("splits body and citation by the em-dash line", () => {
    const r = parsePullQuote(
      "Demand for Blackwell is staggering.\n— JENSEN HUANG · EARNINGS CALL · 14:32 UTC",
    );
    expect(r.text).toBe("Demand for Blackwell is staggering.");
    expect(r.attribution).toBe("JENSEN HUANG");
    expect(r.source).toBe("EARNINGS CALL");
    expect(r.timestamp).toBe("14:32 UTC");
  });

  it("accepts a -- prefix as the citation marker", () => {
    const r = parsePullQuote("Quote text.\n-- Author");
    expect(r.text).toBe("Quote text.");
    expect(r.attribution).toBe("Author");
    expect(r.source).toBeNull();
    expect(r.timestamp).toBeNull();
  });

  it("returns nulls when there is no citation line", () => {
    const r = parsePullQuote("Just a quote with no citation.");
    expect(r.text).toBe("Just a quote with no citation.");
    expect(r.attribution).toBeNull();
    expect(r.source).toBeNull();
    expect(r.timestamp).toBeNull();
  });
});

describe("PullQuote", () => {
  it("renders the body and the joined citation", () => {
    render(
      <PullQuote
        text="Demand for Blackwell is staggering."
        attribution="JENSEN HUANG"
        source="EARNINGS CALL"
        timestamp="14:32 UTC"
      />,
    );
    expect(
      screen.getByText("Demand for Blackwell is staggering."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("— JENSEN HUANG · EARNINGS CALL · 14:32 UTC"),
    ).toBeInTheDocument();
  });

  it("omits the citation line when no parts are present", () => {
    render(<PullQuote text="Solo quote." />);
    expect(screen.getByText("Solo quote.")).toBeInTheDocument();
    expect(screen.queryByText(/—/)).toBeNull();
  });
});
