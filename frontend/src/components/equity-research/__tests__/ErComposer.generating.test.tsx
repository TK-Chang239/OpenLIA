import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { ErComposer } from "../ErComposer";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string, d?: unknown) => (typeof d === "string" ? d : k) }),
}));

const BASE = {
  value: "",
  onChange: () => undefined,
  onSubmit: () => undefined,
  onStop: vi.fn(),
  placeholder: "Run in progress…",
  mode: "stock_initiation" as const,
  length: "normal" as const,
  onModeClick: () => undefined,
  templateLabel: "Stock Initiation",
};

describe("ErComposer generating affordance", () => {
  test("shows the Stop button and the generating mode-pill marker while streaming", () => {
    render(<ErComposer {...BASE} isStreaming />);
    expect(screen.getByLabelText("chat.aria_stop_generating")).toBeInTheDocument();
    expect(screen.getByTestId("er-composer-mode-pill")).toHaveAttribute("data-generating", "true");
  });

  test("mode pill is not marked generating when idle", () => {
    render(<ErComposer {...BASE} isStreaming={false} />);
    expect(screen.getByTestId("er-composer-mode-pill")).toHaveAttribute("data-generating", "false");
  });
});
