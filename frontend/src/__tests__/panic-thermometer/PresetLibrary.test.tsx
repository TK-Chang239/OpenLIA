import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PresetLibrary } from "../../components/panic-thermometer/PresetLibrary";

describe("PresetLibrary", () => {
  const presets = [
    { id: "s-1", user_id: null, name: "oil::ma_relative", description: null, is_shipped: true },
    { id: "u-1", user_id: "u", name: "my-config", description: null, is_shipped: false },
  ];

  it("calls onSaveAs when Save current is clicked", () => {
    const onSaveAs = vi.fn();
    render(
      <PresetLibrary
        presets={presets}
        onApply={() => {}}
        onDelete={() => {}}
        onSaveAs={onSaveAs}
      />,
    );
    fireEvent.change(screen.getByTestId("preset-save-name"), {
      target: { value: "snapshot-1" },
    });
    fireEvent.click(screen.getByTestId("preset-save-btn"));
    expect(onSaveAs).toHaveBeenCalledWith("snapshot-1");
  });

  it("triggers rename flow", () => {
    const onRename = vi.fn();
    render(
      <PresetLibrary
        presets={presets}
        onApply={() => {}}
        onDelete={() => {}}
        onRename={onRename}
      />,
    );
    fireEvent.click(screen.getByTestId("rename-btn-u-1"));
    const input = screen.getByTestId("rename-input-u-1");
    fireEvent.change(input, { target: { value: "renamed" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onRename).toHaveBeenCalledWith("u-1", "renamed");
  });
});
