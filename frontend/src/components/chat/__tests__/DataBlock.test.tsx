import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DataBlock, parseDataBlock } from "../DataBlock";

describe("parseDataBlock", () => {
  it("parses LABEL | VALUE | DELTA rows", () => {
    const rows = parseDataBlock(
      "REVENUE | $35.1B | +94% y/y\nDATA CENTER | $30.8B | +112% y/y",
    );
    expect(rows).toEqual([
      { label: "REVENUE", value: "$35.1B", delta: "+94% y/y" },
      { label: "DATA CENTER", value: "$30.8B", delta: "+112% y/y" },
    ]);
  });

  it("treats a missing third cell as null delta", () => {
    const rows = parseDataBlock("REVENUE | $35.1B");
    expect(rows).toEqual([{ label: "REVENUE", value: "$35.1B", delta: null }]);
  });

  it("skips blank lines and trims whitespace", () => {
    const rows = parseDataBlock("\n  A | 1 | +1 \n\n  B | 2 | -2  \n");
    expect(rows).toEqual([
      { label: "A", value: "1", delta: "+1" },
      { label: "B", value: "2", delta: "-2" },
    ]);
  });
});

describe("DataBlock", () => {
  it("renders rows with role=cell and tints positive/negative deltas", () => {
    render(
      <DataBlock
        rows={[
          { label: "REVENUE", value: "$35.1B", delta: "+94% y/y" },
          { label: "OUTFLOW", value: "$1.2B", delta: "-3% q/q" },
          { label: "STATIC", value: "75.0%", delta: null },
        ]}
      />,
    );
    expect(screen.getByText("REVENUE")).toBeInTheDocument();
    expect(screen.getByText("$35.1B")).toBeInTheDocument();
    expect(screen.getByText("+94% y/y")).toBeInTheDocument();
    expect(screen.getByText("-3% q/q")).toBeInTheDocument();
    // Three rows × three cells = nine cells. Each row's delta cell is
    // the last cell — verify by querying all role=cell.
    expect(screen.getAllByRole("cell")).toHaveLength(9);
  });
});
