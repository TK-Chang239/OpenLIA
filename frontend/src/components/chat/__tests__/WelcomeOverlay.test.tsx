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
});
