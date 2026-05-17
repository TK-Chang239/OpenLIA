import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useBeforeUnloadBeacon } from "./useBeforeUnloadBeacon";

describe("useBeforeUnloadBeacon", () => {
  it("sendBeacon to /notifications/presence-close on beforeunload", () => {
    const sendBeacon = vi.fn();
    (navigator as any).sendBeacon = sendBeacon;
    renderHook(() => useBeforeUnloadBeacon());
    window.dispatchEvent(new Event("beforeunload"));
    expect(sendBeacon).toHaveBeenCalledWith("/notifications/presence-close");
  });
});
