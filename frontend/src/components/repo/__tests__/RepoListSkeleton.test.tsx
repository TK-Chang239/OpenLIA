import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { RepoListSkeleton } from "../RepoListSkeleton";

describe("RepoListSkeleton", () => {
  it("renders eight rows", () => {
    const { container } = render(<RepoListSkeleton />);
    const rows = container.querySelectorAll("li");
    expect(rows).toHaveLength(8);
  });

  it("uses the shared shimmer skeleton on placeholders", () => {
    const { container } = render(<RepoListSkeleton />);
    expect(container.querySelectorAll(".ol-skeleton").length).toBeGreaterThan(0);
  });
});
