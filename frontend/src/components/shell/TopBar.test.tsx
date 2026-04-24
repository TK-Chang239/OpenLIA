import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import { TopBar } from "./TopBar";

describe("TopBar", () => {
  it("renders breadcrumb segments with last as strong", () => {
    render(
      <MemoryRouter>
        <TopBar crumbs={["Home", "Morning Briefing"]} stamps={["TUE · 08:14 UTC"]} live />
      </MemoryRouter>,
    );
    expect(screen.getByText("Home")).toBeInTheDocument();
    const last = screen.getByText("Morning Briefing");
    expect(last.tagName).toBe("STRONG");
    expect(screen.getByText(/LIVE_FEED_ACTIVE/)).toBeInTheDocument();
  });

  it("omits the live pill when live is false", () => {
    render(
      <MemoryRouter>
        <TopBar crumbs={["Home"]} stamps={[]} live={false} />
      </MemoryRouter>,
    );
    expect(screen.queryByText(/LIVE_FEED_ACTIVE/)).toBeNull();
  });
});
