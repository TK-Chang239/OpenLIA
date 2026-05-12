import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { TemplatePickerSection } from "../TemplatePickerSection";
import type { ErTemplate } from "../../../api/equity-research";

vi.mock("../../../api/equity-research", async () => {
  const actual = await vi.importActual<typeof import("../../../api/equity-research")>(
    "../../../api/equity-research",
  );
  return {
    ...actual,
    listErTemplates: vi.fn(),
    uploadErTemplate: vi.fn(),
    patchErTemplate: vi.fn(),
    deleteErTemplate: vi.fn(),
    fetchErTemplateExtractedText: vi.fn(),
  };
});

import {
  listErTemplates,
  uploadErTemplate,
} from "../../../api/equity-research";

const FAKE_GLOBAL: ErTemplate = {
  id: "g1",
  owner_scope: "global",
  owner_user_id: null,
  created_by_user_id: "admin",
  name: "Firm-wide template",
  compatible_modes: ["stock_initiation"],
  raw_filename: "fw.docx",
  raw_mime: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  raw_size_bytes: 12345,
  char_count: 9000,
  estimated_tokens: 3000,
  created_at: "2026-05-11T00:00:00Z",
  updated_at: "2026-05-11T00:00:00Z",
};

const FAKE_USER: ErTemplate = {
  id: "u1",
  owner_scope: "user",
  owner_user_id: "u1",
  created_by_user_id: "u1",
  name: "My private playbook",
  compatible_modes: ["stock_initiation", "stock_update"],
  raw_filename: "mine.md",
  raw_mime: "text/markdown",
  raw_size_bytes: 4000,
  char_count: 4000,
  estimated_tokens: 1000,
  created_at: "2026-05-12T00:00:00Z",
  updated_at: "2026-05-12T00:00:00Z",
};

describe("TemplatePickerSection", () => {
  beforeEach(() => {
    vi.mocked(listErTemplates).mockResolvedValue([FAKE_GLOBAL, FAKE_USER]);
    vi.mocked(uploadErTemplate).mockReset();
  });

  it("renders Default plus compatible templates with badges and token counts", async () => {
    render(
      <TemplatePickerSection
        mode="stock_initiation"
        selectedId="default"
        onSelectedIdChange={() => {}}
        isAdmin={false}
      />,
    );
    await waitFor(() => screen.getByText("Firm-wide template"));
    expect(screen.getByText("Default")).toBeInTheDocument();
    expect(screen.getByText("Firm-wide template")).toBeInTheDocument();
    expect(screen.getByText("My private playbook")).toBeInTheDocument();
    expect(screen.getByText("Global")).toBeInTheDocument();
    expect(screen.getByText("Mine")).toBeInTheDocument();
    expect(screen.getByText(/3,000 tokens/)).toBeInTheDocument();
  });

  it("filters templates by current mode", async () => {
    render(
      <TemplatePickerSection
        mode="sector_research"
        selectedId="default"
        onSelectedIdChange={() => {}}
        isAdmin={false}
      />,
    );
    await waitFor(() => expect(screen.queryByText("Loading templates…")).toBeNull());
    expect(screen.queryByText("Firm-wide template")).toBeNull();
    expect(screen.queryByText("My private playbook")).toBeNull();
  });

  it("invokes onSelectedIdChange when a template is picked", async () => {
    const onChange = vi.fn();
    render(
      <TemplatePickerSection
        mode="stock_initiation"
        selectedId="default"
        onSelectedIdChange={onChange}
        isAdmin={false}
      />,
    );
    await waitFor(() => screen.getByText("My private playbook"));
    fireEvent.click(screen.getByText("My private playbook"));
    expect(onChange).toHaveBeenCalledWith("u1");
  });

  it("hides scope radio for non-admin users in the upload form", async () => {
    render(
      <TemplatePickerSection
        mode="stock_initiation"
        selectedId="default"
        onSelectedIdChange={() => {}}
        isAdmin={false}
      />,
    );
    await waitFor(() => screen.getByText("Add template"));
    expect(screen.queryByText(/Global \(admin\)/)).toBeNull();
  });
});
