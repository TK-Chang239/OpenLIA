import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RegisterForm } from "./RegisterForm";
import { AuthProvider } from "../../auth/AuthContext";

function renderForm(inviteToken = "tok_xyz") {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <RegisterForm inviteToken={inviteToken} />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("RegisterForm", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("rejects mismatched passwords before submitting", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    renderForm();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "b@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "Abcdefg1" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "Abcdefg2" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() =>
      expect(screen.getByText(/passwords do not match/i)).toBeTruthy(),
    );
  });

  it("surfaces invite_invalid as banner", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // session probe
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            code: "invite_invalid",
            message: "This invite link is no longer valid. Contact your administrator for a new one.",
          }),
          { status: 403, headers: { "Content-Type": "application/json" } },
        ),
      ) as unknown as typeof fetch;

    renderForm();

    // Wait for auth to settle (session probe resolves)
    await waitFor(() =>
      expect(screen.getByLabelText("Email")).toBeTruthy(),
    );

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "b@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toMatch(/no longer valid/),
    );
  });

  it("omits display_name from POST body when input is blank", async () => {
    const spy = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // session probe
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            user_id: "u1",
            email: "b@x.com",
            display_name: "b",
            is_admin: false,
            must_change_password: false,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      );
    global.fetch = spy as unknown as typeof fetch;

    renderForm();
    await waitFor(() => expect(screen.getByLabelText("Email")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "b@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => expect(spy.mock.calls.length).toBeGreaterThanOrEqual(2));

    const registerCall = spy.mock.calls.find(
      (c) => typeof c[0] === "string" && c[0].includes("/auth/register"),
    );
    expect(registerCall).toBeTruthy();
    const init = registerCall![1] as RequestInit;
    const body = JSON.parse(String(init.body));
    expect(body.display_name).toBeUndefined();
  });

  it("wires aria-describedby on email when invalid", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    renderForm();
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "bad" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() =>
      expect(
        (screen.getByLabelText("Email") as HTMLInputElement).getAttribute(
          "aria-describedby",
        ),
      ).toBe("email-error"),
    );
  });

  it("toggles aria-busy on submit button during submission", async () => {
    let resolveCall: (resp: Response) => void = () => undefined;
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // session probe
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            resolveCall = resolve;
          }),
      ) as unknown as typeof fetch;
    renderForm();
    await waitFor(() => expect(screen.getByLabelText("Email")).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "b@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "Abcdefg1!" },
    });
    const button = screen.getByRole("button", { name: /create account/i });
    fireEvent.click(button);
    await waitFor(() =>
      expect(button.getAttribute("aria-busy")).toBe("true"),
    );
    resolveCall(
      new Response(
        JSON.stringify({
          user_id: "u1",
          email: "b@x.com",
          display_name: "b",
          is_admin: false,
          must_change_password: false,
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );
    await waitFor(() =>
      expect(button.getAttribute("aria-busy")).toBe("false"),
    );
  });

  it("renders offline banner when fetch rejects with TypeError", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockRejectedValueOnce(new TypeError("Failed to fetch")) as unknown as typeof fetch;
    renderForm();
    await waitFor(() => expect(screen.getByLabelText("Email")).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "b@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toMatch(
        /Can't reach the server/,
      ),
    );
  });
});
