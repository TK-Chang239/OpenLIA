import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RegisterPage } from "./RegisterPage";
import { AuthProvider } from "../auth/AuthContext";

describe("RegisterPage", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("redirects when no invite param", () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    render(
      <MemoryRouter initialEntries={["/register"]}>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.queryByLabelText("Confirm Password")).toBeNull();
  });

  it("renders RegisterForm with invite param", () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    render(
      <MemoryRouter initialEntries={["/register?invite=tok_abcdefgh"]}>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByLabelText("Confirm Password")).toBeTruthy();
  });
});
