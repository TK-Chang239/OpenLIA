import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WizardShell } from "./WizardShell";

describe("WizardShell", () => {
  it("renders title + step indicator + children", () => {
    render(
      <WizardShell title="Welcome" stepIndex={0} totalSteps={5}>
        <p>step body</p>
      </WizardShell>,
    );
    expect(screen.getByRole("dialog", { name: "Welcome" })).toBeInTheDocument();
    expect(screen.getByText("Step 1 of 5")).toBeInTheDocument();
    expect(screen.getByText("step body")).toBeInTheDocument();
  });

  it("progress bar reflects stepIndex/totalSteps", () => {
    render(
      <WizardShell title="Models" stepIndex={2} totalSteps={5}>
        <p>body</p>
      </WizardShell>,
    );
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "2");
    expect(bar).toHaveAttribute("aria-valuemax", "5");
  });
});
