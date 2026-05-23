import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { V23ClarifyQuestion } from "../../api/equity-research-v2-3";

import { V23ClarifyModal } from "./V23ClarifyModal";

const QS: V23ClarifyQuestion[] = [
  {
    id: "fy",
    question: "Which fiscal year for the comp set?",
    why_blocking: "Drives the comps baseline.",
    default: "FY2025",
  },
  {
    id: "include_sec",
    question: "Include the recent SEC filing?",
    why_blocking: "Changes risk section weighting.",
    default: "Yes",
  },
];

function setup(overrides: Partial<React.ComponentProps<typeof V23ClarifyModal>> = {}) {
  const onChange = vi.fn();
  const onSubmit = vi.fn();
  const onUseDefaults = vi.fn();
  const onDismiss = vi.fn();
  render(
    <V23ClarifyModal
      questions={QS}
      answers={{}}
      busy={false}
      onChange={onChange}
      onSubmit={onSubmit}
      onUseDefaults={onUseDefaults}
      onDismiss={onDismiss}
      {...overrides}
    />,
  );
  return { onChange, onSubmit, onUseDefaults, onDismiss };
}

describe("V23ClarifyModal", () => {
  it("renders every pending question with its default as placeholder", () => {
    setup();
    for (const q of QS) {
      const input = screen.getByTestId(
        `er-v2-3-clarify-modal-${q.id}`,
      ) as HTMLInputElement;
      expect(input.placeholder).toBe(q.default);
    }
  });

  it("Continue fires onSubmit", () => {
    const { onSubmit } = setup();
    fireEvent.click(screen.getByTestId("er-v2-3-clarify-modal-submit"));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("Use defaults fires onUseDefaults", () => {
    const { onUseDefaults } = setup();
    fireEvent.click(screen.getByTestId("er-v2-3-clarify-modal-defaults"));
    expect(onUseDefaults).toHaveBeenCalledTimes(1);
  });

  it("backdrop click + Esc dismiss without cancelling", () => {
    const { onDismiss } = setup();
    fireEvent.click(screen.getByTestId("er-v2-3-clarify-modal-backdrop"));
    expect(onDismiss).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onDismiss).toHaveBeenCalledTimes(2);
  });

  it("busy disables every action so a stuck submit can't double-fire", () => {
    setup({ busy: true });
    expect(
      (screen.getByTestId("er-v2-3-clarify-modal-submit") as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(
      (screen.getByTestId("er-v2-3-clarify-modal-defaults") as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(
      (screen.getByTestId("er-v2-3-clarify-modal-cancel") as HTMLButtonElement)
        .disabled,
    ).toBe(true);
  });
});
