import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { LoginForm } from "./LoginForm";
import { AuthProvider } from "../../auth/AuthContext";

function renderInProvider(
  inviteToken?: string,
  policyMode?: "open" | "invite_only" | "closed",
) {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <LoginForm inviteToken={inviteToken} policyMode={policyMode} />
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
      expect(screen.getByRole("alert").textContent).toMatch(
        /Try again in 15 minutes\./,
      ),
    );
  });

  it("hides sign-up link when policy mode is closed", () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    renderInProvider("abc", "closed");
    expect(screen.queryByText(/sign up/i)).toBeNull();
  });

  it("shows sign-up link when policy mode is invite_only and invite present", () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    renderInProvider("abc", "invite_only");
    expect(screen.getByText(/sign up/i)).toBeTruthy();
  });

  it("hides sign-up link when invite missing even with open policy", () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    renderInProvider(undefined, "open");
    expect(screen.queryByText(/sign up/i)).toBeNull();
  });

  it("wires aria-describedby to inline email error id", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    renderInProvider();
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "notemail" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "anypw" },
    });
    fireEvent.click(screen.getByRole("button", { name: /log in/i }));
    await waitFor(() =>
      expect(
        (screen.getByLabelText("Email") as HTMLInputElement).getAttribute(
          "aria-describedby",
        ),
      ).toBe("email-error"),
    );
  });

  it("toggles aria-busy on the submit button while submitting", async () => {
    let resolveLogin: (resp: Response) => void = () => undefined;
    global.fetch = vi.fn().mockImplementation(() => {
      return new Promise<Response>((resolve) => {
        resolveLogin = resolve;
      });
    }) as unknown as typeof fetch;
    renderInProvider();
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "a@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "pw12345!" },
    });
    const button = screen.getByRole("button", { name: /log in/i });
    fireEvent.click(button);
    await waitFor(() =>
      expect(button.getAttribute("aria-busy")).toBe("true"),
    );
    resolveLogin(new Response(null, { status: 401 }));
    await waitFor(() =>
      expect(button.getAttribute("aria-busy")).toBe("false"),
    );
  });

  it("renders offline banner when fetch throws TypeError", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // session probe
      .mockRejectedValueOnce(new TypeError("Failed to fetch")) as unknown as typeof fetch;
    renderInProvider();
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "a@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "pw12345!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /log in/i }));
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toMatch(
        /Can't reach the server/,
      ),
    );
  });

  it("renders 5xx server-error banner", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({}), {
          status: 500,
          headers: { "Content-Type": "application/json" },
        }),
      ) as unknown as typeof fetch;
    renderInProvider();
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "a@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "pw12345!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /log in/i }));
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toMatch(
        /Something went wrong on our end/,
      ),
    );
  });
});
