import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { InstallBuiltinForm } from "../InstallBuiltinForm";
import type { BuiltinTemplate } from "../../../api/connectors";
import * as connectorsApi from "../../../api/connectors";

const TEMPLATE: BuiltinTemplate = {
  template_id: "firecrawl",
  display_name: "Firecrawl",
  category: "web_search",
  api_key_env_var: "FIRECRAWL_API_KEY",
  covered_need_ids: [],
};

describe("InstallBuiltinForm", () => {
  it("renders the env-var label and an api_key input", () => {
    render(
      <InstallBuiltinForm
        template={TEMPLATE}
        onCancel={() => {}}
        onInstalled={() => {}}
      />,
    );
    expect(screen.getByText("FIRECRAWL_API_KEY")).toBeInTheDocument();
    expect(screen.getByLabelText(/api key/i)).toBeInTheDocument();
  });

  it("calls installBuiltin and onInstalled on submit", async () => {
    const installStub = vi
      .spyOn(connectorsApi, "installBuiltin")
      .mockResolvedValue({
        id: "1",
        provider_id: "firecrawl",
        display_name: "Firecrawl",
        source: "built_in",
        category: "web_search",
        status: "validated",
        last_error: null,
        cached_tools_count: 0,
      });
    const onInstalled = vi.fn();

    render(
      <InstallBuiltinForm
        template={TEMPLATE}
        onCancel={() => {}}
        onInstalled={onInstalled}
      />,
    );
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: "user-key" },
    });
    fireEvent.click(screen.getByRole("button", { name: /install/i }));

    await waitFor(() =>
      expect(installStub).toHaveBeenCalledWith({
        template_id: "firecrawl",
        api_key: "user-key",
      }),
    );
    await waitFor(() => expect(onInstalled).toHaveBeenCalled());
  });

  it("shows an error message if install fails", async () => {
    vi.spyOn(connectorsApi, "installBuiltin").mockRejectedValue(
      new Error("nope"),
    );
    render(
      <InstallBuiltinForm
        template={TEMPLATE}
        onCancel={() => {}}
        onInstalled={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: "x" },
    });
    fireEvent.click(screen.getByRole("button", { name: /install/i }));
    expect(await screen.findByText(/nope/i)).toBeInTheDocument();
  });
});
