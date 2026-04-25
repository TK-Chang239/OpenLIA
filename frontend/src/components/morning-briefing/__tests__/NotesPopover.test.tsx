import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { NotesPopover } from "../NotesPopover";

describe("NotesPopover", () => {
  it("opens, edits notes, Done saves", async () => {
    const onSave = vi.fn();
    render(
      <NotesPopover topic="AAPL" notes="initial" onSave={onSave}>
        <button type="button">trigger</button>
      </NotesPopover>,
    );
    fireEvent.click(screen.getByText("trigger"));
    const ta = await screen.findByTestId("notes-popover-textarea-AAPL");
    expect((ta as HTMLTextAreaElement).value).toBe("initial");
    fireEvent.change(ta, { target: { value: "updated" } });
    fireEvent.click(screen.getByTestId("notes-popover-done-AAPL"));
    expect(onSave).toHaveBeenCalledWith("updated");
    await waitFor(() =>
      expect(
        screen.queryByTestId("notes-popover-textarea-AAPL"),
      ).not.toBeInTheDocument(),
    );
  });
});
