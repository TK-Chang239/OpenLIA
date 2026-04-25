import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { WelcomeOverlay } from "../WelcomeOverlay";

describe("WelcomeOverlay", () => {
  it("renders greeting and sub-text", () => {
    render(<WelcomeOverlay greeting="Good morning" subtext="What can I do?" chips={[]} onChipClick={() => {}} />);
    expect(screen.getByText("Good morning")).toBeInTheDocument();
    expect(screen.getByText("What can I do?")).toBeInTheDocument();
  });

  it("renders chips and fires onChipClick with the chip value", () => {
    const onClick = vi.fn();
    render(
      <WelcomeOverlay
        greeting="Hi"
        subtext=""
        chips={[
          { label: "Market today", value: "What moved the market today?" },
          { label: "Top movers", value: "Top movers" },
        ]}
        onChipClick={onClick}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /market today/i }));
    expect(onClick).toHaveBeenCalledWith("What moved the market today?");
  });

  it("respects prefers-reduced-motion (zero stagger on chips)", () => {
    // Stub matchMedia → reduce.
    const originalMatch = window.matchMedia;
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes("reduce"),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      onchange: null,
      dispatchEvent: vi.fn(),
    })) as typeof window.matchMedia;
    render(
      <WelcomeOverlay
        greeting="Hi"
        subtext=""
        chips={[{ label: "x", value: "x" }]}
        onChipClick={() => {}}
      />,
    );
    expect(screen.getByTestId("welcome-overlay")).toBeInTheDocument();
    window.matchMedia = originalMatch;
  });
});
