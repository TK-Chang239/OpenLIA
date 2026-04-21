import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Home } from "lucide-react";
import { NavItem } from "./NavItem";

function renderAt(route: string, ui: React.ReactElement) {
  return render(<MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>);
}

describe("NavItem", () => {
  it("renders label in expanded mode and marks active on matching path", () => {
    renderAt(
      "/repository",
      <NavItem
        label="Repository"
        icon={Home}
        path="/repository"
        collapsed={false}
        hasUnread={false}
      />,
    );
    const link = screen.getByRole("link", { name: /repository/i });
    expect(link.getAttribute("aria-current")).toBe("page");
  });

  it("hides label and exposes aria-label in collapsed mode", () => {
    renderAt(
      "/home",
      <NavItem
        label="Home"
        icon={Home}
        path="/"
        collapsed={true}
        hasUnread={false}
      />,
    );
    expect(screen.queryByText("Home")).toBeNull();
    expect(screen.getByRole("link")).toHaveAttribute("aria-label", "Home");
  });

  it("renders a notification dot only when hasUnread is true", () => {
    const { rerender } = renderAt(
      "/",
      <NavItem
        label="Morning Briefing"
        icon={Home}
        path="/morning-briefing"
        collapsed={false}
        hasUnread={false}
      />,
    );
    expect(screen.queryByTestId("nav-item-dot")).toBeNull();

    rerender(
      <MemoryRouter initialEntries={["/"]}>
        <NavItem
          label="Morning Briefing"
          icon={Home}
          path="/morning-briefing"
          collapsed={false}
          hasUnread={true}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("nav-item-dot")).toBeInTheDocument();
  });
});
