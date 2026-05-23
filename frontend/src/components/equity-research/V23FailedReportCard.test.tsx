import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { V23FailedReportCard } from "./V23FailedReportCard";

describe("V23FailedReportCard", () => {
  it("shows the failing stage label and engine error message", () => {
    render(
      <V23FailedReportCard
        runId="run-deadbeef-1234"
        failedStage="verify"
        lastError="VERIFY: hard issue not resolved after 1 retry."
        retryCount={1}
        onRestart={() => {}}
      />,
    );
    expect(screen.getByText(/Run failed during Verify/i)).toBeInTheDocument();
    expect(screen.getByTestId("er-v2-3-failed-card-error")).toHaveTextContent(
      /hard issue not resolved/i,
    );
    expect(screen.getByText(/1 retry attempt/i)).toBeInTheDocument();
  });

  it("falls back to a generic message when last_error is empty", () => {
    render(
      <V23FailedReportCard
        runId="run-x"
        failedStage={null}
        lastError={null}
        retryCount={0}
        onRestart={() => {}}
      />,
    );
    expect(screen.getByText(/Run failed during Pipeline/i)).toBeInTheDocument();
    expect(screen.getByTestId("er-v2-3-failed-card-error")).toHaveTextContent(
      /unspecified failure/i,
    );
  });

  it("Restart fires onRestart", () => {
    const onRestart = vi.fn();
    render(
      <V23FailedReportCard
        runId="r"
        failedStage="plan"
        lastError="bad outline"
        retryCount={0}
        onRestart={onRestart}
      />,
    );
    fireEvent.click(screen.getByTestId("er-v2-3-failed-card-restart"));
    expect(onRestart).toHaveBeenCalledTimes(1);
  });
});
