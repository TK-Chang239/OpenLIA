import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SaveToRepoButton } from "../SaveToRepoButton";
import * as repoApi from "../../../api/repo";

vi.mock("../../../api/repo");

describe("SaveToRepoButton", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders chip variant with bookmark icon and no label", () => {
    render(<SaveToRepoButton reportId="r1" initialSaved={false} variant="chip" />);
    const btn = screen.getByRole("button", { name: /save to repository/i });
    expect(btn).toBeInTheDocument();
    expect(btn.textContent?.trim()).toBe("");
  });

  it("renders viewer-header variant with a visible label", () => {
    render(<SaveToRepoButton reportId="r1" initialSaved={false} variant="viewer-header" />);
    expect(screen.getByRole("button", { name: /save to repository/i })).toHaveTextContent(/save/i);
  });

  it("calls saveToRepo when clicked in unsaved state and flips to saved", async () => {
    (repoApi.saveToRepo as ReturnType<typeof vi.fn>).mockResolvedValue({ saved: true });
    render(<SaveToRepoButton reportId="r1" initialSaved={false} variant="viewer-header" />);
    fireEvent.click(screen.getByRole("button", { name: /save to repository/i }));
    await waitFor(() => expect(repoApi.saveToRepo).toHaveBeenCalledWith("r1"));
    expect(
      await screen.findByRole("button", { name: /remove from repository/i }),
    ).toBeInTheDocument();
  });

  it("calls unsaveFromRepo when clicked in saved state and flips to unsaved", async () => {
    (repoApi.unsaveFromRepo as ReturnType<typeof vi.fn>).mockResolvedValue({ saved: false });
    render(<SaveToRepoButton reportId="r1" initialSaved={true} variant="viewer-header" />);
    fireEvent.click(screen.getByRole("button", { name: /remove from repository/i }));
    await waitFor(() => expect(repoApi.unsaveFromRepo).toHaveBeenCalledWith("r1"));
    expect(
      await screen.findByRole("button", { name: /save to repository/i }),
    ).toBeInTheDocument();
  });

  it("shows an error indicator when the call fails and does not flip state", async () => {
    (repoApi.saveToRepo as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("offline"));
    render(<SaveToRepoButton reportId="r1" initialSaved={false} variant="viewer-header" />);
    fireEvent.click(screen.getByRole("button", { name: /save to repository/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not save/i);
    expect(screen.getByRole("button", { name: /save to repository/i })).toBeInTheDocument();
  });

  it("routes to the v3 save endpoint when engine=v3", async () => {
    (repoApi.saveV3RunToRepo as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "x",
      v3_report_id: "v3-1",
      created_at: "2026-05-28T00:00:00Z",
    });
    render(
      <SaveToRepoButton
        reportId="v3-1"
        engine="v3"
        initialSaved={false}
        variant="viewer-header"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /save to repository/i }));
    await waitFor(() =>
      expect(repoApi.saveV3RunToRepo).toHaveBeenCalledWith("v3-1"),
    );
    // v1 endpoint must not be called when engine=v3.
    expect(repoApi.saveToRepo).not.toHaveBeenCalled();
  });

  it("routes to the v3 unsave endpoint when engine=v3 and already saved", async () => {
    (repoApi.unsaveV3RunFromRepo as ReturnType<typeof vi.fn>).mockResolvedValue(
      undefined,
    );
    render(
      <SaveToRepoButton
        reportId="v3-1"
        engine="v3"
        initialSaved={true}
        variant="viewer-header"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /remove from repository/i }));
    await waitFor(() =>
      expect(repoApi.unsaveV3RunFromRepo).toHaveBeenCalledWith("v3-1"),
    );
    expect(repoApi.unsaveFromRepo).not.toHaveBeenCalled();
  });

  it("routes to the eu save endpoint when engine=eu", async () => {
    (repoApi.saveEuRunToRepo as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "x",
      eu_v2_report_id: "eu-1",
      created_at: "2026-05-28T00:00:00Z",
    });
    render(
      <SaveToRepoButton
        reportId="eu-1"
        engine="eu"
        initialSaved={false}
        variant="viewer-header"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /save to repository/i }));
    await waitFor(() =>
      expect(repoApi.saveEuRunToRepo).toHaveBeenCalledWith("eu-1"),
    );
    // v1 endpoint must not be called when engine=eu.
    expect(repoApi.saveToRepo).not.toHaveBeenCalled();
  });

  it("routes to the eu unsave endpoint when engine=eu and already saved", async () => {
    (repoApi.unsaveEuRunFromRepo as ReturnType<typeof vi.fn>).mockResolvedValue(
      undefined,
    );
    render(
      <SaveToRepoButton
        reportId="eu-1"
        engine="eu"
        initialSaved={true}
        variant="viewer-header"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /remove from repository/i }));
    await waitFor(() =>
      expect(repoApi.unsaveEuRunFromRepo).toHaveBeenCalledWith("eu-1"),
    );
    expect(repoApi.unsaveFromRepo).not.toHaveBeenCalled();
  });

  it("routes to the v2 save endpoint when engine=v2", async () => {
    (repoApi.saveV2RunToRepo as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "x",
      pipeline_run_id: "v2-1",
      created_at: "2026-05-28T00:00:00Z",
    });
    render(
      <SaveToRepoButton
        reportId="v2-1"
        engine="v2"
        initialSaved={false}
        variant="viewer-header"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /save to repository/i }));
    await waitFor(() =>
      expect(repoApi.saveV2RunToRepo).toHaveBeenCalledWith("v2-1"),
    );
  });
});
