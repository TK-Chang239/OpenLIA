import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../../../api/earnings-update";
import { OnDemandReportModal } from "../OnDemandReportModal";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("OnDemandReportModal (v2)", () => {
  it("accepts a free-text ticker and starts a run", async () => {
    const startSpy = vi.spyOn(api, "startRun").mockResolvedValue({ report_id: "r1" });
    const onStarted = vi.fn();
    render(<OnDemandReportModal open watchlist={[]} onClose={() => {}} onStarted={onStarted} />);
    fireEvent.change(screen.getByTestId("eu-v2-ondemand-ticker"), { target: { value: "NVDA.US" } });
    fireEvent.click(screen.getByTestId("eu-v2-ondemand-start"));
    await waitFor(() => expect(startSpy).toHaveBeenCalledWith({ ticker: "NVDA.US" }));
    await waitFor(() => expect(onStarted).toHaveBeenCalledWith("r1", "NVDA.US"));
  });
});
