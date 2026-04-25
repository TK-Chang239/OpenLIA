import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { RepoListSkeleton } from "../RepoListSkeleton";

describe("RepoListSkeleton", () => {
  it("renders eight rows", () => {
    const { container } = render(<RepoListSkeleton />);
    const rows = container.querySelectorAll("li");
    expect(rows).toHaveLength(8);
  });

  it("uses animate-pulse styling on placeholders", () => {
    const { container } = render(<RepoListSkeleton />);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });
});
