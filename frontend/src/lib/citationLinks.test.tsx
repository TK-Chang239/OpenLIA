import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import { CitationTableContext, linkifyCitations, useLinkedProse } from "./citationLinks";

const TABLE = [
  { source_id: "web_2", title: "Reuters piece", url: "https://reuters.com/a" },
  { source_id: "eodhd_1", title: "EODHD news", url: null },
];

describe("linkifyCitations", () => {
  test("resolved markers become numbered superscript links", () => {
    render(<p>{linkifyCitations("Growth held up. [^web_2]", TABLE)}</p>);
    const link = screen.getByRole("link", { name: "[1]" });
    expect(link).toHaveAttribute("href", "https://reuters.com/a");
    expect(link).toHaveAttribute("title", "Reuters piece");
  });

  test("url-less citations render a plain numbered superscript", () => {
    const { container } = render(<p>{linkifyCitations("CPI printed 3.4%.[^eodhd_1]", TABLE)}</p>);
    expect(container.textContent).toBe("CPI printed 3.4%.[2]");
    expect(container.querySelector("a")).toBeNull();
  });

  test("unknown markers are stripped", () => {
    const { container } = render(<p>{linkifyCitations("Claim.[^ghost_9] Next.", TABLE)}</p>);
    expect(container.textContent).toBe("Claim. Next.");
  });

  test("no table degrades to a strip", () => {
    const { container } = render(<p>{linkifyCitations("Text. [^web_2]", null)}</p>);
    expect(container.textContent).toBe("Text.");
  });
});

describe("useLinkedProse", () => {
  function Probe({ value }: { value: string }) {
    const prose = useLinkedProse();
    return <p>{prose(value)}</p>;
  }

  test("resolves against the context table", () => {
    render(
      <CitationTableContext.Provider value={TABLE}>
        <Probe value="Debt is extreme. [^web_2]" />
      </CitationTableContext.Provider>,
    );
    expect(screen.getByRole("link", { name: "[1]" })).toBeInTheDocument();
  });

  test("strips without a provider", () => {
    const { container } = render(<Probe value="Debt is extreme. [^web_2]" />);
    expect(container.textContent).toBe("Debt is extreme.");
  });
});
