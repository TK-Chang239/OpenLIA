import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RuleEditor } from "../../components/panic-thermometer/RuleEditor";

vi.mock("../../api/panic-thermometer", () => ({
  parseFormula: vi.fn().mockResolvedValue({ ok: true, identifiers: ["price"] }),
}));

describe("RuleEditor", () => {
  const baseRules = [
    { status: "red" as const, formula: "price > 85", label: "elevated" },
    { status: "green" as const, formula: "true", label: "normal" },
  ];

  it("adds a new rule", () => {
    const onChange = vi.fn();
    render(<RuleEditor panel="oil" rules={baseRules} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("rule-add"));
    expect(onChange).toHaveBeenCalledWith([
      ...baseRules,
      { status: "green", formula: "true", label: "" },
    ]);
  });

  it("deletes a rule", () => {
    const onChange = vi.fn();
    render(<RuleEditor panel="oil" rules={baseRules} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("rule-delete-0"));
    expect(onChange).toHaveBeenCalledWith([baseRules[1]]);
  });

  it("reorders rules", () => {
    const onChange = vi.fn();
    render(<RuleEditor panel="oil" rules={baseRules} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("rule-down-0"));
    expect(onChange).toHaveBeenCalledWith([baseRules[1], baseRules[0]]);
  });
});
