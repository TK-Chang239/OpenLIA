import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { TopBar } from "../TopBar";
import { ChatHeaderRegistryTestHarness } from "./_chatHeaderHarness";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string, o?: { defaultValue?: string }) => o?.defaultValue ?? k }),
}));

describe("TopBar generating pill", () => {
  test("renders a GENERATING pill when the chat header reports generating", () => {
    render(
      <ChatHeaderRegistryTestHarness
        value={{
          departmentId: "equity_research_v3",
          activeSessionId: "run-1",
          chatTitle: "AAPL",
          onSelect: () => undefined,
          onCreate: () => undefined,
          generating: true,
        }}
      >
        <TopBar crumbs={["Equity Research"]} />
      </ChatHeaderRegistryTestHarness>,
    );
    expect(screen.getByText("GENERATING")).toBeInTheDocument();
  });

  test("does not render a GENERATING pill when generating is false/absent", () => {
    render(
      <ChatHeaderRegistryTestHarness
        value={{
          departmentId: "equity_research_v3",
          activeSessionId: "run-1",
          chatTitle: "AAPL",
          onSelect: () => undefined,
          onCreate: () => undefined,
        }}
      >
        <TopBar crumbs={["Equity Research"]} />
      </ChatHeaderRegistryTestHarness>,
    );
    expect(screen.queryByText("GENERATING")).toBeNull();
  });
});
