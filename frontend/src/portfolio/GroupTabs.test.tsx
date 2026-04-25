import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ALL_GROUP, GroupTabs } from "./GroupTabs";

describe("GroupTabs", () => {
  it("renders 'All' tab as the implicit first entry", () => {
    render(
      <GroupTabs
        groups={["Tech"]}
        active={ALL_GROUP}
        onSelect={() => {}}
        onCreate={() => {}}
        onRename={() => {}}
        onDelete={() => {}}
      />,
    );
    expect(screen.getByTestId("group-tab-all")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("group-tab-Tech")).toBeInTheDocument();
  });

  it("opens the new-group input when clicking the + button", () => {
    render(
      <GroupTabs
        groups={[]}
        active={ALL_GROUP}
        onSelect={() => {}}
        onCreate={() => {}}
        onRename={() => {}}
        onDelete={() => {}}
      />,
    );
    fireEvent.click(screen.getByTestId("group-tab-new"));
    expect(screen.getByTestId("group-tab-new-input")).toBeInTheDocument();
  });

  it("calls onCreate on Enter", () => {
    const onCreate = vi.fn();
    render(
      <GroupTabs
        groups={[]}
        active={ALL_GROUP}
        onSelect={() => {}}
        onCreate={onCreate}
        onRename={() => {}}
        onDelete={() => {}}
      />,
    );
    fireEvent.click(screen.getByTestId("group-tab-new"));
    const input = screen.getByTestId("group-tab-new-input");
    fireEvent.change(input, { target: { value: "Banks" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onCreate).toHaveBeenCalledWith("Banks");
  });

  it("opens context menu on right-click for a user group", () => {
    render(
      <GroupTabs
        groups={["Tech"]}
        active={ALL_GROUP}
        onSelect={() => {}}
        onCreate={() => {}}
        onRename={() => {}}
        onDelete={() => {}}
      />,
    );
    fireEvent.contextMenu(screen.getByTestId("group-tab-Tech"));
    expect(screen.getByTestId("group-context-menu")).toBeInTheDocument();
  });
});
