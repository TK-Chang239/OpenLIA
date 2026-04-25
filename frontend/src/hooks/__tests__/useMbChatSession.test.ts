import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/morning-briefing";
import { useMbChatSession } from "../useMbChatSession";

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("useMbChatSession", () => {
  it("starts with no sessionId and no error (loading)", () => {
    vi.spyOn(api, "resolveChatSession").mockReturnValue(
      new Promise(() => {}),
    );
    const { result } = renderHook(() => useMbChatSession());
    expect(result.current.sessionId).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("resolves session id from POST when none exists", async () => {
    const spy = vi
      .spyOn(api, "resolveChatSession")
      .mockResolvedValue({ session_id: "sess-new" });
    const { result } = renderHook(() => useMbChatSession());
    await waitFor(() => expect(result.current.sessionId).toBe("sess-new"));
    expect(spy).toHaveBeenCalledOnce();
    expect(result.current.error).toBeNull();
  });

  it("sets error when resolveChatSession rejects", async () => {
    vi.spyOn(api, "resolveChatSession").mockRejectedValue(
      new Error("network"),
    );
    const { result } = renderHook(() => useMbChatSession());
    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.error?.message).toBe("network");
    expect(result.current.sessionId).toBeNull();
  });
});
