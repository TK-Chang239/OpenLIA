import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ResponseLengthPicker } from "../ResponseLengthPicker";

const patchSession = vi.fn();

vi.mock("../../../api/chat", async () => {
  const actual: Record<string, unknown> = await vi.importActual("../../../api/chat");
  return {
    ...actual,
    patchSession: (...args: unknown[]) => patchSession(...args),
  };
});

describe("ResponseLengthPicker", () => {
  beforeEach(() => {
    patchSession.mockReset().mockResolvedValue({ ok: true });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("defaults to Normal when no initial value is provided", () => {
    render(<ResponseLengthPicker sessionId="s1" />);
    expect(screen.getByRole("button", { name: /response length/i })).toHaveTextContent(
      /normal/i,
    );
  });

  it("renders the initial value from the session row", () => {
    render(<ResponseLengthPicker sessionId="s1" initialValue="concise" />);
    expect(screen.getByRole("button", { name: /response length/i })).toHaveTextContent(
      /concise/i,
    );
  });

  it("renders Detailed when the session row says detailed", () => {
    render(<ResponseLengthPicker sessionId="s1" initialValue="detailed" />);
    expect(screen.getByRole("button", { name: /response length/i })).toHaveTextContent(
      /detailed/i,
    );
  });

  it("syncs to a new initial value after the session GET resolves", () => {
    const { rerender } = render(
      <ResponseLengthPicker sessionId="s1" initialValue={null} />,
    );
    expect(screen.getByRole("button", { name: /response length/i })).toHaveTextContent(
      /normal/i,
    );
    rerender(<ResponseLengthPicker sessionId="s1" initialValue="detailed" />);
    expect(screen.getByRole("button", { name: /response length/i })).toHaveTextContent(
      /detailed/i,
    );
  });

  it("resets when switching to a different session id", () => {
    const { rerender } = render(
      <ResponseLengthPicker sessionId="s1" initialValue="concise" />,
    );
    rerender(<ResponseLengthPicker sessionId="s2" initialValue={null} />);
    expect(screen.getByRole("button", { name: /response length/i })).toHaveTextContent(
      /normal/i,
    );
  });
});
