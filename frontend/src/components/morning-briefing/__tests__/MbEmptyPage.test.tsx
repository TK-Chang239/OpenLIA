import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MbEmptyPage } from "../feed/MbEmptyPage";

describe("MbEmptyPage", () => {
  it("fires onRunNow and onOpenLibrary", () => {
    const onRunNow = vi.fn();
    const onOpenLibrary = vi.fn();
    render(<MbEmptyPage onRunNow={onRunNow} onOpenLibrary={onOpenLibrary} />);
    fireEvent.click(screen.getByTestId("mb-empty-run-now"));
    fireEvent.click(screen.getByTestId("mb-empty-open-library"));
    expect(onRunNow).toHaveBeenCalledTimes(1);
    expect(onOpenLibrary).toHaveBeenCalledTimes(1);
  });
});
