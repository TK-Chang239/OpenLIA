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
});
