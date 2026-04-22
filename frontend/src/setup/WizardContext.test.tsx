import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { WizardProvider, useWizard } from "./WizardContext";

beforeEach(() => {
  vi.restoreAllMocks();
});

const jsonResponse = (body: unknown) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

function Probe() {
  const wizard = useWizard();
  if (wizard.state === "loading") return <div>loading</div>;
  return (
    <div>
      mode:{wizard.status.mode} step:{wizard.status.current_step}
    </div>
  );
}

describe("WizardContext", () => {
  it("fetches status on mount", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({
        mode: "company",
        wizard_completed: false,
        current_step: "admin",
        completed_steps: ["mode"],
        env_overrides: {},
      }),
    );

    render(
      <WizardProvider>
        <Probe />
      </WizardProvider>,
    );
    await waitFor(() => expect(screen.getByText(/mode:company/)).toBeInTheDocument());
    expect(screen.getByText(/step:admin/)).toBeInTheDocument();
  });

  it("exposes refresh() that re-fetches status", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({
        mode: "personal",
        wizard_completed: false,
        current_step: "mode",
        completed_steps: [],
        env_overrides: {},
      }),
    );

    function Refresher() {
      const wizard = useWizard();
      if (wizard.state === "loading") return <div>loading</div>;
      return <button onClick={wizard.refresh}>refresh</button>;
    }

    render(
      <WizardProvider>
        <Refresher />
      </WizardProvider>,
    );
    await waitFor(() => screen.getByText("refresh"));
    screen.getByText("refresh").click();
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2));
  });
});
