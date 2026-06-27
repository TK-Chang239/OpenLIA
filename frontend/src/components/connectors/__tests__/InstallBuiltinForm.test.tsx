import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { InstallBuiltinForm } from "../InstallBuiltinForm";
import type { BuiltinTemplate } from "../../../api/connectors";
import * as connectorsApi from "../../../api/connectors";
import { ApiError } from "../../../api/client";

const conflictError = (existingId: string) =>
  new ApiError(409, "HTTP 409", {
    detail: {
      message: "connector already exists",
      existing_id: existingId,
      provider_id: "firecrawl",
      source: "built_in",
    },
  });

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

  it("on 409 conflict, offers to replace the existing connector instead of a raw error", async () => {
    vi.spyOn(connectorsApi, "installBuiltin").mockRejectedValue(
      conflictError("c1"),
    );
    const onInstalled = vi.fn();
    render(
      <InstallBuiltinForm
        template={TEMPLATE}
        onCancel={() => {}}
        onInstalled={onInstalled}
      />,
    );
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: "k" },
    });
    fireEvent.click(screen.getByRole("button", { name: /install/i }));

    expect(await screen.findByText(/already installed/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /replace/i }),
    ).toBeInTheDocument();
    expect(onInstalled).not.toHaveBeenCalled();
  });

  it("replace deletes the existing connector and reinstalls with the entered key", async () => {
    const installStub = vi
      .spyOn(connectorsApi, "installBuiltin")
      .mockRejectedValueOnce(conflictError("c1"))
      .mockResolvedValueOnce({
        id: "c2",
        provider_id: "firecrawl",
        display_name: "Firecrawl",
        source: "built_in",
        category: "web_search",
        status: "validated",
        last_error: null,
        cached_tools_count: 0,
      });
    const deleteStub = vi
      .spyOn(connectorsApi, "deleteConnector")
      .mockResolvedValue(undefined);
    const onInstalled = vi.fn();

    render(
      <InstallBuiltinForm
        template={TEMPLATE}
        onCancel={() => {}}
        onInstalled={onInstalled}
      />,
    );
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: "k" },
    });
    fireEvent.click(screen.getByRole("button", { name: /install/i }));
    fireEvent.click(await screen.findByRole("button", { name: /replace/i }));

    await waitFor(() => expect(deleteStub).toHaveBeenCalledWith("c1"));
    await waitFor(() => expect(onInstalled).toHaveBeenCalled());
    expect(installStub).toHaveBeenCalledTimes(2);
  });
});
