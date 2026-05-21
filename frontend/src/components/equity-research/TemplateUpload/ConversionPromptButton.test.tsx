import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ConversionPromptButton } from "./ConversionPromptButton";

vi.mock("../../../api/report-templates", () => ({
  fetchConversionPrompt: vi.fn(),
}));

import { fetchConversionPrompt } from "../../../api/report-templates";

describe("ConversionPromptButton", () => {
  beforeEach(() => {
    vi.mocked(fetchConversionPrompt).mockReset();
  });

  it("renders Convert button text initially", () => {
    render(<ConversionPromptButton />);
    expect(screen.getByRole("button", { name: "Convert" })).toBeInTheDocument();
  });

  it("shows Copied state after click", async () => {
    vi.mocked(fetchConversionPrompt).mockResolvedValue("the prompt text");
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      writable: true,
      configurable: true,
    });

    render(<ConversionPromptButton />);
    fireEvent.click(screen.getByRole("button", { name: "Convert" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Copied!" })).toBeInTheDocument();
    });
    expect(writeText).toHaveBeenCalledWith("the prompt text");
  });
});
