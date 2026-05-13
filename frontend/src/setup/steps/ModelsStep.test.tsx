import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModelsStep } from "./ModelsStep";

describe("ModelsStep", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("starts on the keys screen with Next disabled until a key is added", async () => {
    render(
      <ModelsStep
        totalSteps={5}
        enabledDepartmentIds={["equity_research"]}
        systemRoleIds={["chat"]}
        onBack={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();

    await userEvent.type(screen.getByPlaceholderText(/Label/i), "My OpenAI");
    await userEvent.type(screen.getByPlaceholderText(/^API key$/i), "sk-test");
    await userEvent.click(screen.getByText(/Save key/i));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /next/i })).toBeEnabled(),
    );
  });

  it("flows keys -> register -> assign and saves with the new payload shape", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() =>
        Promise.resolve(
          new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      );
    const onSaved = vi.fn();

    render(
      <ModelsStep
        totalSteps={5}
        enabledDepartmentIds={["equity_research"]}
        systemRoleIds={["chat"]}
        onBack={vi.fn()}
        onSaved={onSaved}
      />,
    );

    // Screen 1: keys.
    await userEvent.type(screen.getByPlaceholderText(/Label/i), "My OpenAI");
    await userEvent.type(screen.getByPlaceholderText(/^API key$/i), "sk-test");
    await userEvent.click(screen.getByText(/Save key/i));
    await userEvent.click(screen.getByRole("button", { name: /next/i }));

    // Screen 2: register.
    await waitFor(() =>
      expect(screen.getByText(/Register Models/i)).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("button", { name: /add model/i }));
    await userEvent.type(screen.getByPlaceholderText(/model id/i), "gpt-5.4-pro");
    await userEvent.type(screen.getByPlaceholderText(/display name/i), "GPT 5.4 Pro");
    await userEvent.click(screen.getByRole("button", { name: /^save$/i }));
    await userEvent.click(screen.getByRole("button", { name: /next/i }));

    // Screen 3: assign.
    await waitFor(() =>
      expect(screen.getByText(/Assign Default Models/i)).toBeInTheDocument(),
    );
    await userEvent.selectOptions(screen.getByLabelText(/equity research/i), "gpt-5.4-pro");
    await userEvent.selectOptions(screen.getByLabelText(/^chat$/i), "gpt-5.4-pro");
    await userEvent.click(screen.getByRole("button", { name: /finish/i }));

    await waitFor(() => expect(onSaved).toHaveBeenCalled());

    const lastCall = fetchSpy.mock.calls.find(([url]) =>
      String(url).includes("/api/setup/models"),
    );
    expect(lastCall).toBeTruthy();
    const body = JSON.parse((lastCall![1] as RequestInit).body as string);
    expect(body).toMatchObject({
      models: [
        {
          provider_kind: "openai",
          api_key: "sk-test",
          model_ref: "gpt-5.4-pro",
          display_name: "GPT 5.4 Pro",
        },
      ],
      department_defaults: { equity_research: "gpt-5.4-pro" },
      system_role_defaults: { chat: "gpt-5.4-pro" },
    });
  });

  it("restores saved keys on remount (back-navigation case)", async () => {
    const first = render(
      <ModelsStep
        totalSteps={5}
        enabledDepartmentIds={["equity_research"]}
        systemRoleIds={["chat"]}
        onBack={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    await userEvent.type(screen.getByPlaceholderText(/Label/i), "My OpenAI");
    await userEvent.type(screen.getByPlaceholderText(/^API key$/i), "sk-test");
    await userEvent.click(screen.getByText(/Save key/i));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /next/i })).toBeEnabled(),
    );
    first.unmount();

    render(
      <ModelsStep
        totalSteps={5}
        enabledDepartmentIds={["equity_research"]}
        systemRoleIds={["chat"]}
        onBack={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /edit key/i })).toBeInTheDocument();
  });
});
