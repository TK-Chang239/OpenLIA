import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  CategoryRequirementsPanel,
  aggregateRequirements,
} from "../CategoryRequirementsPanel";
import type { ConnectorRow } from "../../../api/connectors";
import type { DepartmentHealth } from "../../../api/dept-health";

const mkConn = (
  category: ConnectorRow["category"],
  status: ConnectorRow["status"] = "validated",
): ConnectorRow => ({
  id: "c-" + category + "-" + status,
  provider_id: "p",
  display_name: "P",
  source: "built_in",
  category,
  status,
  last_error: null,
  cached_tools_count: 0,
});

const mkHealth = (
  id: string,
  required_categories: string[],
  required_any_of: string[][] = [],
): DepartmentHealth => ({
  department_id: id,
  status: "active",
  reason: null,
  missing_categories: [],
  unresolved_needs: [],
  required_categories,
  required_any_of,
  unsatisfied_any_of: [],
});

describe("aggregateRequirements", () => {
  it("flags FINANCIAL as required when any dept lists it", () => {
    const healths = {
      equity_research: mkHealth("equity_research", ["financial"]),
    };
    const rows = aggregateRequirements(healths, []);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      category: "financial",
      necessity: "required",
      validatedCount: 0,
      requiredByDepts: ["equity_research"],
    });
  });

  it("counts validated connectors per category", () => {
    const healths = {
      equity_research: mkHealth("equity_research", ["financial"]),
    };
    const rows = aggregateRequirements(healths, [
      mkConn("financial"),
      mkConn("financial", "pending"),
      mkConn("financial"),
    ]);
    expect(rows[0].validatedCount).toBe(2);
  });

  it("classifies any_of-only categories as 'alternative'", () => {
    const healths = {
      morning_briefing: mkHealth(
        "morning_briefing",
        ["financial"],
        [["news", "web_search"]],
      ),
    };
    const rows = aggregateRequirements(healths, []);
    const news = rows.find((r) => r.category === "news");
    const ws = rows.find((r) => r.category === "web_search");
    expect(news?.necessity).toBe("alternative");
    expect(ws?.necessity).toBe("alternative");
  });

  it("required wins over alternative when category appears in both", () => {
    const healths = {
      macro_research: mkHealth("macro_research", ["financial", "web_search"]),
      morning_briefing: mkHealth(
        "morning_briefing",
        ["financial"],
        [["news", "web_search"]],
      ),
    };
    const rows = aggregateRequirements(healths, []);
    const ws = rows.find((r) => r.category === "web_search");
    expect(ws?.necessity).toBe("required");
    expect(ws?.requiredByDepts).toEqual(["macro_research"]);
  });
});

describe("<CategoryRequirementsPanel>", () => {
  it("renders nothing when no requirements exist", () => {
    const { container } = render(
      <CategoryRequirementsPanel connectors={[]} healths={{}} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("marks a required category met when ≥1 validated connector matches", () => {
    const healths = {
      equity_research: mkHealth("equity_research", ["financial"]),
    };
    render(
      <CategoryRequirementsPanel
        connectors={[mkConn("financial")]}
        healths={healths}
      />,
    );
    const row = screen.getByTestId("category-row-financial");
    expect(row.dataset.met).toBe("true");
  });

  it("marks a required category not-met when no validated connector exists", () => {
    const healths = {
      macro_research: mkHealth("macro_research", ["financial", "web_search"]),
    };
    render(
      <CategoryRequirementsPanel
        connectors={[mkConn("financial")]}
        healths={healths}
      />,
    );
    expect(screen.getByTestId("category-row-financial").dataset.met).toBe("true");
    expect(screen.getByTestId("category-row-web_search").dataset.met).toBe(
      "false",
    );
  });

  it("marks an any_of category satisfied when its sibling is validated", () => {
    // MB any_of: (news, web_search). Only web_search validated → both rows met.
    const healths = {
      morning_briefing: mkHealth(
        "morning_briefing",
        ["financial"],
        [["news", "web_search"]],
      ),
    };
    render(
      <CategoryRequirementsPanel
        connectors={[mkConn("financial"), mkConn("web_search")]}
        healths={healths}
      />,
    );
    expect(screen.getByTestId("category-row-news").dataset.met).toBe("true");
    expect(screen.getByTestId("category-row-web_search").dataset.met).toBe(
      "true",
    );
  });

  it("lists the alternative category when explaining an any_of row", () => {
    const healths = {
      morning_briefing: mkHealth(
        "morning_briefing",
        ["financial"],
        [["news", "web_search"]],
      ),
    };
    render(<CategoryRequirementsPanel connectors={[]} healths={healths} />);
    const newsRow = screen.getByTestId("category-row-news");
    expect(newsRow.textContent).toContain("Web search");
  });
});
