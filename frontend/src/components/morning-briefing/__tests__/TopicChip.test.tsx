import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TopicChip } from "../TopicChip";

describe("TopicChip", () => {
  it("fires onClick on body click", () => {
    const onClick = vi.fn();
    render(
      <TopicChip
        topic="AAPL"
        hasNotes={false}
        onClick={onClick}
        onRemove={() => {}}
      />,
    );
    fireEvent.click(screen.getByTestId("topic-chip-body-AAPL"));
    expect(onClick).toHaveBeenCalled();
  });

  it("fires onRemove on × click", () => {
    const onRemove = vi.fn();
    render(
      <TopicChip
        topic="AAPL"
        hasNotes={false}
        onClick={() => {}}
        onRemove={onRemove}
      />,
    );
    fireEvent.click(screen.getByLabelText("Remove AAPL"));
    expect(onRemove).toHaveBeenCalled();
  });

  it("shows dot when hasNotes is true", () => {
    const { rerender } = render(
      <TopicChip
        topic="AAPL"
        hasNotes={true}
        onClick={() => {}}
        onRemove={() => {}}
      />,
    );
    expect(screen.getByTestId("topic-chip-dot-AAPL")).toBeInTheDocument();
    rerender(
      <TopicChip
        topic="AAPL"
        hasNotes={false}
        onClick={() => {}}
        onRemove={() => {}}
      />,
    );
    expect(screen.queryByTestId("topic-chip-dot-AAPL")).not.toBeInTheDocument();
  });
});
