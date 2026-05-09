import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReleasesTable } from "../sections/ReleasesTable";
import { releaseRows } from "../../../lib/panic_thermometer/copy/releases";

describe("ReleasesTable", () => {
  it("renders the section header and column headers", () => {
    render(<ReleasesTable rows={releaseRows} />);
    expect(screen.getByText("Macro releases · last 7 days")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "When" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Release" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Actual" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Surprise" })).toBeInTheDocument();
  });

  it("renders one row per release", () => {
    render(<ReleasesTable rows={releaseRows} />);
    const rows = screen.getAllByRole("row");
    expect(rows.length).toBe(releaseRows.length + 1);
  });

  it("renders surprise tags such as 'hot' and 'tone'", () => {
    render(<ReleasesTable rows={releaseRows} />);
    expect(screen.getAllByText("hot").length).toBeGreaterThan(0);
    expect(screen.getByText("tone")).toBeInTheDocument();
  });

  it("renders release source sublines", () => {
    render(<ReleasesTable rows={releaseRows} />);
    expect(screen.getAllByText("BLS · Apr").length).toBeGreaterThan(0);
    expect(screen.getByText("BEA · Mar")).toBeInTheDocument();
  });
});
