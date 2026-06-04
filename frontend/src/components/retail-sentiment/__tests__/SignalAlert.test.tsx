import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SignalAlert } from "../SignalAlert";

describe("SignalAlert", () => {
  it("renders signal name and note", () => {
    render(
      <SignalAlert
        name="Momentum crossover"
        severity="info"
        note="5d MA crossed above 20d."
      />,
    );
    expect(screen.getByText("Momentum crossover")).toBeInTheDocument();
    expect(screen.getByText("5d MA crossed above 20d.")).toBeInTheDocument();
  });

  it("shows ALERT label for alert severity", () => {
    render(
      <SignalAlert
        name="Extreme buzz"
        severity="alert"
        note="Volume 5x above 30d average."
      />,
    );
    expect(screen.getByTestId("signal-alert")).toBeInTheDocument();
    expect(screen.getByText("ALERT")).toBeInTheDocument();
  });

  it("shows CAUTION label for caution severity", () => {
    render(
      <SignalAlert
        name="Buzz spike"
        severity="caution"
        note="Volume elevated."
      />,
    );
    expect(screen.getByTestId("signal-caution")).toBeInTheDocument();
  });
});
