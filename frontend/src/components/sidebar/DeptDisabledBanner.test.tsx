import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { DeptDisabledBanner } from "./DeptDisabledBanner";
import { useDeptHealth } from "../../store/dept-health";

beforeEach(() => {
  useDeptHealth.setState({
    healths: {},
    loaded: false,
    loading: false,
    error: null,
  });
});

describe("DeptDisabledBanner", () => {
  it("renders nothing when dept health is not loaded", () => {
    render(
      <MemoryRouter>
        <DeptDisabledBanner departmentId="macro_research" />
      </MemoryRouter>,
    );
    expect(
      screen.queryByTestId("dept-disabled-banner-macro_research"),
    ).not.toBeInTheDocument();
  });

  it("renders nothing when dept is active", () => {
    useDeptHealth.setState({
      healths: {
        macro_research: {
          department_id: "macro_research",
          status: "active",
          reason: null,
          missing_categories: [],
          unresolved_needs: [],
        },
      },
      loaded: true,
      loading: false,
      error: null,
    });
    render(
      <MemoryRouter>
        <DeptDisabledBanner departmentId="macro_research" />
      </MemoryRouter>,
    );
    expect(
      screen.queryByTestId("dept-disabled-banner-macro_research"),
    ).not.toBeInTheDocument();
  });

  it("renders a banner with reason and Settings link when dept is disabled", () => {
    useDeptHealth.setState({
      healths: {
        macro_research: {
          department_id: "macro_research",
          status: "disabled",
          reason: "Missing required categories: financial",
          missing_categories: ["financial"],
          unresolved_needs: [],
        },
      },
      loaded: true,
      loading: false,
      error: null,
    });
    render(
      <MemoryRouter>
        <DeptDisabledBanner departmentId="macro_research" />
      </MemoryRouter>,
    );
    expect(
      screen.getByTestId("dept-disabled-banner-macro_research"),
    ).toBeInTheDocument();
    expect(screen.getByText(/missing required categories/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /settings.*connectors/i }),
    ).toHaveAttribute("href", "/settings/admin/connectors");
  });
});
