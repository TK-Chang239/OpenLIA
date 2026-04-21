import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { LoginForm } from "./LoginForm";
import { AuthProvider } from "../../auth/AuthContext";

function renderInProvider(inviteToken?: string) {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <LoginForm inviteToken={inviteToken} />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("LoginForm", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("disables submit until email + password non-empty", () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 }));
    global.fetch = global.fetch as unknown as typeof fetch;
    renderInProvider();
    const button = screen.getByRole("button", { name: /log in/i });
    expect((button as HTMLButtonElement).disabled).toBe(true);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "a@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "pw12345!" },
    });
    expect((button as HTMLButtonElement).disabled).toBe(false);
  });

  it("shows inline email error for bad format", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    renderInProvider();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "notemail" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "pw12345!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /log in/i }));

    await waitFor(() =>
      expect(screen.getByText(/enter a valid email/i)).toBeTruthy(),
    );
  });

  it("shows the sign-up link only when inviteToken is present", () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    const { rerender } = renderInProvider();
    expect(screen.queryByText(/sign up/i)).toBeNull();
    rerender(
      <MemoryRouter>
        <AuthProvider>
          <LoginForm inviteToken="abc" />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText(/sign up/i)).toBeTruthy();
  });

  it("renders lockout banner from account_locked code", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // initial session probe
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            code: "account_locked",
            message: "Too many failed attempts.",
            metadata: { retry_after_seconds: 900 },
          }),
          { status: 423, headers: { "Content-Type": "application/json" } },
        ),
      ) as unknown as typeof fetch;

    renderInProvider();

    await waitFor(() =>
      expect(
        (screen.getByRole("button", { name: /log in/i }) as HTMLButtonElement)
          .disabled,
      ).toBe(true),
    );

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "a@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "pw12345!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /log in/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toMatch(/Too many/),
    );
  });
});
