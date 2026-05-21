import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ClarifierModal } from "./ClarifierModal";
import type { ClarifierOutput } from "../../../api/clarifier";

const sampleWarning: ClarifierOutput = {
  questions: [],
  blocking_warnings: [
    {
      capability_id: "extra_passes",
      detected_phrase: "devil's advocate pass",
      user_message: "Extra LLM passes are not supported in this version.",
      available_actions: ["proceed_without", "cancel_and_edit", "clarify"],
    },
  ],
  notices: [],
  detected_intents: ["extras"],
};

const emptyOutput: ClarifierOutput = {
  questions: [],
  blocking_warnings: [],
  notices: [],
  detected_intents: [],
};

describe("ClarifierModal", () => {
  it("submit is disabled until all warnings have an action", () => {
    render(
      <ClarifierModal
        output={sampleWarning}
        round={1}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const submit = screen.getByRole("button", { name: /submit/i });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: /proceed without/i }));
    expect(submit).toBeEnabled();
  });

  it("round counter is shown", () => {
    render(
      <ClarifierModal
        output={sampleWarning}
        round={2}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText(/Round 2 of 3/)).toBeInTheDocument();
  });

  it("clarify button is hidden after round 3", () => {
    render(
      <ClarifierModal
        output={sampleWarning}
        round={3}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.queryByRole("button", { name: /clarify/i })).not.toBeInTheDocument();
  });

  it("clicking clarify reveals textarea", () => {
    render(
      <ClarifierModal
        output={sampleWarning}
        round={1}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /clarify/i }));
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("multiple_choice question renders select", () => {
    const output: ClarifierOutput = {
      ...emptyOutput,
      questions: [
        {
          id: "q1",
          text: "Which time horizon?",
          kind: "multiple_choice",
          options: ["1Y", "3Y", "5Y"],
        },
      ],
    };
    render(
      <ClarifierModal output={output} round={1} onSubmit={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("free_text question renders input", () => {
    const output: ClarifierOutput = {
      ...emptyOutput,
      questions: [
        {
          id: "q2",
          text: "Any additional context?",
          kind: "free_text",
        },
      ],
    };
    render(
      <ClarifierModal output={output} round={1} onSubmit={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("cancel button calls onCancel", () => {
    const onCancel = vi.fn();
    render(
      <ClarifierModal
        output={sampleWarning}
        round={1}
        onSubmit={vi.fn()}
        onCancel={onCancel}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
