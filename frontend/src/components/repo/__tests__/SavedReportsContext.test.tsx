import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import {
  SavedReportsProvider,
  useSavedReportsOptional,
} from "../SavedReportsContext";
import * as repoApi from "../../../api/repo";

vi.mock("../../../api/repo");

function Probe({ id }: { id: string }) {
  const ctx = useSavedReportsOptional();
  return <div data-testid="probe">{ctx?.isMbSaved(id) ? "saved" : "no"}</div>;
}

describe("SavedReportsContext MB bucket", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    (repoApi.listRepoItems as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [] });
    (repoApi.listSavedV2Runs as ReturnType<typeof vi.fn>).mockResolvedValue({ saved_run_ids: [] });
    (repoApi.listSavedV3Runs as ReturnType<typeof vi.fn>).mockResolvedValue({ saved_report_ids: [] });
    (repoApi.listSavedEuRuns as ReturnType<typeof vi.fn>).mockResolvedValue({ saved_report_ids: [] });
    (repoApi.listSavedMbRuns as ReturnType<typeof vi.fn>).mockResolvedValue({ saved_report_ids: [] });
  });

  it("hydrates isMbSaved from listSavedMbRuns", async () => {
    (repoApi.listSavedMbRuns as ReturnType<typeof vi.fn>).mockResolvedValue({
      saved_report_ids: ["mb-1"],
    });
    render(
      <SavedReportsProvider>
        <Probe id="mb-1" />
      </SavedReportsProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("probe")).toHaveTextContent("saved"));
  });
});
