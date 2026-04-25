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

  it("renders error banner on 500 instead of neutral success", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({}), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;

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
      expect(screen.getByRole("alert").textContent).toMatch(
        /Something went wrong on our end/,
      ),
    );
    // Success status banner must NOT be present.
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("renders offline banner on TypeError", async () => {
    global.fetch = vi
      .fn()
      .mockRejectedValue(new TypeError("Failed to fetch")) as unknown as typeof fetch;

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
      expect(screen.getByRole("alert").textContent).toMatch(
        /Can't reach the server/,
      ),
    );
  });

  it("wires aria-describedby on email input when invalid", async () => {
    render(
      <MemoryRouter>
        <ForgotPasswordForm />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "bogus" },
    });
    fireEvent.click(screen.getByRole("button", { name: /request reset/i }));
    await waitFor(() =>
      expect(
        (screen.getByLabelText("Email") as HTMLInputElement).getAttribute(
          "aria-describedby",
        ),
      ).toBe("email-error"),
    );
  });

  it("toggles aria-busy during submission", async () => {
    let resolveCall: (resp: Response) => void = () => undefined;
    global.fetch = vi.fn().mockImplementation(
      () =>
        new Promise<Response>((resolve) => {
          resolveCall = resolve;
        }),
    ) as unknown as typeof fetch;

    render(
      <MemoryRouter>
        <ForgotPasswordForm />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "a@x.com" },
    });
    const button = screen.getByRole("button", { name: /request reset/i });
    fireEvent.click(button);
    await waitFor(() =>
      expect(button.getAttribute("aria-busy")).toBe("true"),
    );
    resolveCall(new Response(null, { status: 204 }));
    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toMatch(/your admin/i),
    );
  });
});
