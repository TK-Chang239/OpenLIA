import { Check, AlertCircle } from "lucide-react";
import type { ConnectorRow, Category } from "../../api/connectors";
import type { DepartmentHealth } from "../../api/dept-health";

interface Props {
  connectors: ConnectorRow[];
  healths: Record<string, DepartmentHealth>;
}

interface CategoryRow {
  category: Category;
  necessity: "required" | "alternative";
  validatedCount: number;
  requiredByDepts: string[];
  anyOfGroups: string[][];
}

const CATEGORY_LABELS: Record<Category, string> = {
  financial: "Financial data",
  news: "News headlines",
  social: "Social posts",
  web_search: "Web search / scraping",
};

const DEPT_LABELS: Record<string, string> = {
  equity_research: "Equity Research",
  earnings_update: "Earnings Update",
  morning_briefing: "Morning Briefings",
  panic_thermometer: "Panic Thermometer",
  macro_research: "Macro Research",
  retail_sentiment: "Retail Sentiment",
  secretary: "Secretary",
};

const deptLabel = (id: string): string => DEPT_LABELS[id] ?? id;
const catLabel = (c: string): string =>
  CATEGORY_LABELS[c as Category] ?? c;

export function aggregateRequirements(
  healths: Record<string, DepartmentHealth>,
  connectors: ConnectorRow[],
): CategoryRow[] {
  const validatedByCat = new Map<Category, number>();
  for (const c of connectors) {
    if (c.status !== "validated") continue;
    validatedByCat.set(c.category, (validatedByCat.get(c.category) ?? 0) + 1);
  }

  const requiredByMap = new Map<Category, Set<string>>();
  const anyOfMap = new Map<Category, string[][]>();

  for (const h of Object.values(healths)) {
    for (const c of h.required_categories ?? []) {
      const cat = c as Category;
      if (!requiredByMap.has(cat)) requiredByMap.set(cat, new Set());
      requiredByMap.get(cat)!.add(h.department_id);
    }
    for (const group of h.required_any_of ?? []) {
      for (const c of group) {
        const cat = c as Category;
        if (!anyOfMap.has(cat)) anyOfMap.set(cat, []);
        anyOfMap.get(cat)!.push(group);
      }
    }
  }

  const allCats = new Set<Category>([
    ...requiredByMap.keys(),
    ...anyOfMap.keys(),
  ]);

  const order: Category[] = ["financial", "news", "web_search", "social"];
  return order
    .filter((c) => allCats.has(c))
    .map((cat) => ({
      category: cat,
      necessity: requiredByMap.has(cat) ? "required" : "alternative",
      validatedCount: validatedByCat.get(cat) ?? 0,
      requiredByDepts: Array.from(requiredByMap.get(cat) ?? []).sort(),
      anyOfGroups: anyOfMap.get(cat) ?? [],
    }));
}

function isAnyOfGroupSatisfied(
  group: string[],
  validatedCats: Set<string>,
): boolean {
  return group.some((c) => validatedCats.has(c));
}

export function CategoryRequirementsPanel({ connectors, healths }: Props) {
  const rows = aggregateRequirements(healths, connectors);
  if (rows.length === 0) return null;

  const validatedCats = new Set(
    connectors.filter((c) => c.status === "validated").map((c) => c.category),
  );

  return (
    <section
      className="rounded-md border border-border-subtle bg-bg-elevated p-3"
      data-testid="category-requirements-panel"
      aria-label="Required connector categories"
    >
      <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-text-secondary">
        Required connector categories
      </h4>
      <ul className="space-y-2">
        {rows.map((row) => {
          const hardMet = row.necessity === "required" && row.validatedCount > 0;
          const altGroupSatisfied =
            row.necessity === "alternative" &&
            row.anyOfGroups.some((g) => isAnyOfGroupSatisfied(g, validatedCats));
          const met = hardMet || altGroupSatisfied;

          return (
            <li
              key={row.category}
              className="flex items-start gap-2 text-xs"
              data-testid={`category-row-${row.category}`}
              data-met={met ? "true" : "false"}
            >
              <span className="mt-0.5 shrink-0">
                {met ? (
                  <Check
                    size={14}
                    className="text-feedback-success"
                    aria-label="met"
                  />
                ) : (
                  <AlertCircle
                    size={14}
                    className="text-feedback-warning"
                    aria-label="not met"
                  />
                )}
              </span>
              <span className="flex-1">
                <span className="font-medium text-text-primary">
                  {catLabel(row.category)}
                </span>
                {row.necessity === "required" ? (
                  <span className="ml-1 rounded bg-bg-subtle px-1 py-0.5 text-[10px] text-text-secondary">
                    Required
                  </span>
                ) : (
                  <span className="ml-1 rounded bg-bg-subtle px-1 py-0.5 text-[10px] text-text-secondary">
                    Alternative
                  </span>
                )}
                <span className="ml-2 text-text-secondary">
                  {row.validatedCount > 0
                    ? `${row.validatedCount} validated connector${row.validatedCount === 1 ? "" : "s"}`
                    : "No validated connector yet"}
                </span>
                <div className="mt-0.5 text-text-tertiary">
                  {row.requiredByDepts.length > 0 ? (
                    <span>
                      Required by:{" "}
                      {row.requiredByDepts.map(deptLabel).join(", ")}
                    </span>
                  ) : null}
                  {row.necessity === "alternative" && row.anyOfGroups.length > 0
                    ? (() => {
                        const others = new Set<string>();
                        for (const g of row.anyOfGroups) {
                          for (const c of g) {
                            if (c !== row.category) others.add(c);
                          }
                        }
                        const altList = Array.from(others).map(catLabel).join(" or ");
                        return (
                          <span>
                            {row.requiredByDepts.length > 0 ? " · " : ""}
                            Either this or {altList} satisfies the requirement.
                          </span>
                        );
                      })()
                    : null}
                </div>
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
