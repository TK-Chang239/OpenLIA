import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SettingsDrawer } from "../SettingsDrawer";

describe("SettingsDrawer", () => {
  it("renders thresholds + weights when open", () => {
    render(
      <SettingsDrawer open onClose={() => {}} onSave={async () => {}} />,
    );
    expect(screen.getByTestId("settings-drawer")).toBeInTheDocument();
    expect(screen.getByText(/Thresholds/i)).toBeInTheDocument();
    expect(screen.getByText(/Cross-source weights/i)).toBeInTheDocument();
  });

  it("invokes onSave when Save clicked", async () => {
    const onSave = vi.fn();
    render(<SettingsDrawer open onClose={() => {}} onSave={onSave} />);
    fireEvent.click(screen.getByText("Save"));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
  });
});
