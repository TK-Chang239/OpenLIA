import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DisclaimerModal } from "../DisclaimerModal";

describe("DisclaimerModal", () => {
  it("calls onAccept when 'I understand' is clicked", () => {
    const onAccept = vi.fn();
    render(<DisclaimerModal text="**hello**" onAccept={onAccept} onDecline={() => {}} />);
    fireEvent.click(screen.getByText("I understand"));
    expect(onAccept).toHaveBeenCalledOnce();
  });

  it("calls onDecline when 'Sign out / Quit' is clicked", () => {
    const onDecline = vi.fn();
    render(<DisclaimerModal text="x" onAccept={() => {}} onDecline={onDecline} />);
    fireEvent.click(screen.getByText("Sign out / Quit"));
    expect(onDecline).toHaveBeenCalledOnce();
  });
});
