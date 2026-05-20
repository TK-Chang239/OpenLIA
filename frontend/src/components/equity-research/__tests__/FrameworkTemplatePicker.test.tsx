import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FrameworkTemplatePicker } from "../FrameworkTemplatePicker";
import * as api from "../../../api/report-templates";

const SAMPLE_TEMPLATES = [
  {
    id: "t1",
    name: "Stock Initiation v3",
    template_spec: {},
    source_markdown: null,
    created_at: "2026-05-20T00:00:00Z",
    updated_at: "2026-05-20T00:00:00Z",
  },
  {
    id: "t2",
    name: "Chinese 28 framework",
    template_spec: {},
    source_markdown: null,
    created_at: "2026-05-20T00:00:00Z",
    updated_at: "2026-05-20T00:00:00Z",
  },
];

describe("FrameworkTemplatePicker", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the default option plus the user's templates", async () => {
    vi.spyOn(api, "listReportTemplates").mockResolvedValue(SAMPLE_TEMPLATES);

    render(<FrameworkTemplatePicker selectedId={null} onChange={() => {}} />);

    const select = (await screen.findByTestId(
      "framework-template-picker",
    )) as HTMLSelectElement;
    await waitFor(() =>
      expect(
        Array.from(select.options).map((o) => o.text),
      ).toEqual(["Default", "Stock Initiation v3", "Chinese 28 framework"]),
    );
    expect(select.value).toBe("__default__");
  });

  it("emits the chosen template id when the user picks one", async () => {
    vi.spyOn(api, "listReportTemplates").mockResolvedValue(SAMPLE_TEMPLATES);
    const onChange = vi.fn();

    render(<FrameworkTemplatePicker selectedId={null} onChange={onChange} />);

    const select = (await screen.findByTestId(
      "framework-template-picker",
    )) as HTMLSelectElement;
    await waitFor(() => expect(select.options.length).toBe(3));
    fireEvent.change(select, { target: { value: "t2" } });
    expect(onChange).toHaveBeenCalledWith("t2");
  });

  it("emits null when the user picks the default option", async () => {
    vi.spyOn(api, "listReportTemplates").mockResolvedValue(SAMPLE_TEMPLATES);
    const onChange = vi.fn();

    render(
      <FrameworkTemplatePicker selectedId="t1" onChange={onChange} />,
    );

    const select = (await screen.findByTestId(
      "framework-template-picker",
    )) as HTMLSelectElement;
    await waitFor(() => expect(select.options.length).toBe(3));
    fireEvent.change(select, { target: { value: "__default__" } });
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("clears a stale selection when the template no longer exists", async () => {
    vi.spyOn(api, "listReportTemplates").mockResolvedValue(SAMPLE_TEMPLATES);
    const onChange = vi.fn();

    render(
      <FrameworkTemplatePicker
        selectedId="deleted-id"
        onChange={onChange}
      />,
    );

    await waitFor(() => expect(onChange).toHaveBeenCalledWith(null));
  });
});
