import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RepoListItem } from "../RepoListItem";

const ROW = {
  id: "i1",
  report_id: "r1",
  department: "equity_research",
  title: "AAPL",
  filename: "AAPL.pdf",
  generated_at: "2026-04-20T10:00:00Z",
  saved_at: "2026-04-22T10:00:00Z",
};

describe("RepoListItem", () => {
  it("calls onOpen when row clicked", () => {
    const onOpen = vi.fn();
    render(
      <ul>
        <RepoListItem
          row={ROW}
          downloadUrl="/x"
          onOpen={onOpen}
          onRemove={vi.fn()}
        />
      </ul>,
    );
    fireEvent.click(screen.getByTestId("repo-row"));
    expect(onOpen).toHaveBeenCalledWith(ROW);
  });

  it("does not call onOpen when remove button clicked", () => {
    const onOpen = vi.fn();
    const onRemove = vi.fn();
    render(
      <ul>
        <RepoListItem row={ROW} downloadUrl="/x" onOpen={onOpen} onRemove={onRemove} />
      </ul>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Remove AAPL.pdf/ }));
    expect(onRemove).toHaveBeenCalledWith(ROW);
    expect(onOpen).not.toHaveBeenCalled();
  });

  it("does not call onOpen when download anchor clicked", () => {
    const onOpen = vi.fn();
    render(
      <ul>
        <RepoListItem row={ROW} downloadUrl="/x" onOpen={onOpen} onRemove={vi.fn()} />
      </ul>,
    );
    fireEvent.click(screen.getByRole("link", { name: /Download AAPL.pdf/ }));
    expect(onOpen).not.toHaveBeenCalled();
  });

  it("renders department badge with friendly label", () => {
    render(
      <ul>
        <RepoListItem row={ROW} downloadUrl="/x" onOpen={vi.fn()} onRemove={vi.fn()} />
      </ul>,
    );
    expect(screen.getByTestId("department-badge")).toHaveTextContent("Equity Research");
  });

  it("opens via Enter keyboard shortcut", () => {
    const onOpen = vi.fn();
    render(
      <ul>
        <RepoListItem row={ROW} downloadUrl="/x" onOpen={onOpen} onRemove={vi.fn()} />
      </ul>,
    );
    fireEvent.keyDown(screen.getByTestId("repo-row"), { key: "Enter" });
    expect(onOpen).toHaveBeenCalled();
  });
});
