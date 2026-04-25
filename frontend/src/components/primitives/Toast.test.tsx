import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider, useToast } from "./Toast";

function Pusher({
  title,
  withUndo,
}: {
  readonly title: string;
  readonly withUndo?: () => void;
}): JSX.Element {
  const toast = useToast();
  return (
    <button
      onClick={() =>
        toast.push({
          title,
          undo: withUndo
            ? { label: "Undo", onClick: withUndo }
            : undefined,
        })
      }
    >
      push
    </button>
  );
}

describe("Toast primitive", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders pushed toasts and auto-dismisses", () => {
    render(
      <ToastProvider>
        <Pusher title="Saved" />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByText("push"));
    expect(screen.getByText("Saved")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(screen.queryByText("Saved")).toBeNull();
  });

  it("invokes undo and dismisses the toast", () => {
    const undo = vi.fn();
    render(
      <ToastProvider>
        <Pusher title="Removed" withUndo={undo} />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByText("push"));
    fireEvent.click(screen.getByText("Undo"));
    expect(undo).toHaveBeenCalled();
    expect(screen.queryByText("Removed")).toBeNull();
  });
});
