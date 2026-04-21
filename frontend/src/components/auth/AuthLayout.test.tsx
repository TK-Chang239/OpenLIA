import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuthLayout } from "./AuthLayout";
import { AuthCard } from "./AuthCard";

describe("AuthLayout + AuthCard", () => {
  it("renders wordmark + card children inside <main>", () => {
    render(
      <AuthLayout>
        <AuthCard>
          <div>FormContent</div>
        </AuthCard>
      </AuthLayout>,
    );
    expect(screen.getByRole("main").getAttribute("aria-label")).toBe(
      "Authentication",
    );
    expect(screen.getByText("LIA")).toBeTruthy();
    expect(screen.getByText("FormContent")).toBeTruthy();
  });
});
