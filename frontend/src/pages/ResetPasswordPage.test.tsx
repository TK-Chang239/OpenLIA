import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ResetPasswordPage } from "./ResetPasswordPage";

describe("ResetPasswordPage", () => {
  it("shows error banner when token missing", () => {
    render(
      <MemoryRouter initialEntries={["/reset-password"]}>
        <ResetPasswordPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole("alert").textContent).toMatch(/invalid/i);
  });

  it("renders the reset form when token present", () => {
    render(
      <MemoryRouter initialEntries={["/reset-password?token=abc"]}>
        <ResetPasswordPage />
      </MemoryRouter>,
    );
    expect(screen.getByLabelText("New Password")).toBeTruthy();
  });
});
