import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Home, Sun } from "lucide-react";
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

  it("renders the acid-yellow rail when route is active", () => {
    render(
      <MemoryRouter initialEntries={["/morning-briefing"]}>
        <NavItem
          label="Morning Briefing"
          icon={Sun}
          path="/morning-briefing"
          collapsed={false}
          hasUnread={false}
        />
      </MemoryRouter>,
    );
    const link = screen.getByRole("link", { current: "page" });
    const rail = link.querySelector("[aria-hidden='true']");
    expect(rail).not.toBeNull();
    expect(rail!.className).toMatch(/absolute|w-\[2px\]/);
  });

  it("shows a Radix tooltip with the label when collapsed and hovered", async () => {
    const user = userEvent.setup();
    renderAt(
      "/",
      <NavItem
        label="Equity Research"
        icon={Home}
        path="/equity-research"
        collapsed={true}
        hasUnread={false}
      />,
    );
    expect(screen.queryByRole("tooltip")).toBeNull();
    await user.hover(screen.getByRole("link"));
    await waitFor(() => {
      const tip = screen.getAllByText("Equity Research");
      expect(tip.length).toBeGreaterThan(0);
    });
    const tooltips = await screen.findAllByRole("tooltip");
    expect(tooltips[0]).toHaveTextContent("Equity Research");
  });
});
