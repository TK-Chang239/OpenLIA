import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ForgotPasswordForm } from "./ForgotPasswordForm";

describe("ForgotPasswordForm", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("always shows neutral confirmation after submit", async () => {
    const spy = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = spy as unknown as typeof fetch;

    render(
      <MemoryRouter>
        <ForgotPasswordForm />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "a@x.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /request reset/i }));

    await waitFor(() =>
      expect(
        screen.getByRole("status").textContent,
      ).toMatch(/your admin has been notified/i),
    );

    expect(spy.mock.calls[0][0]).toBe("/api/auth/password-reset/request");
  });
});
