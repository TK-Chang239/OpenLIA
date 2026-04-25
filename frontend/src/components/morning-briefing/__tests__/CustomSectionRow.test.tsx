import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CustomSectionRow } from "../CustomSectionRow";

describe("CustomSectionRow", () => {
  const section = { id: "abc", title: "T", description: "D" };

  it("edits title and description", () => {
    const onChange = vi.fn();
    render(
      <CustomSectionRow
        section={section}
        onChange={onChange}
        onRemove={() => {}}
      />,
    );
    fireEvent.change(screen.getByTestId("custom-section-title-abc"), {
      target: { value: "New" },
    });
    expect(onChange).toHaveBeenCalledWith({ title: "New" });
    fireEvent.change(screen.getByTestId("custom-section-description-abc"), {
      target: { value: "Desc" },
    });
    expect(onChange).toHaveBeenCalledWith({ description: "Desc" });
  });

  it("fires onRemove via × button", () => {
    const onRemove = vi.fn();
    render(
      <CustomSectionRow
        section={section}
        onChange={() => {}}
        onRemove={onRemove}
      />,
    );
    fireEvent.click(screen.getByLabelText("Remove section"));
    expect(onRemove).toHaveBeenCalled();
  });
});
