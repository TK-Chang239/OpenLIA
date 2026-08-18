import { describe, expect, test } from "vitest";
import { stripCitationMarkers } from "./citations";

describe("stripCitationMarkers", () => {
  test("removes ledger-style markers and tidies spacing", () => {
    expect(
      stripCitationMarkers(
        "TSLA registered 109 mentions. [^web_2] StockTwits assigns 67/100. [^web_10]",
      ),
    ).toBe("TSLA registered 109 mentions. StockTwits assigns 67/100.");
  });

  test("removes adjacent markers with no space", () => {
    expect(stripCitationMarkers("Debt levels are extreme.[^web_21][^web_30]")).toBe(
      "Debt levels are extreme.",
    );
  });

  test("leaves plain text and numeric footnotes untouched", () => {
    expect(stripCitationMarkers("Growth was 16.4% [1] this year.")).toBe(
      "Growth was 16.4% [1] this year.",
    );
  });
});
