import { describe, expect, test, vi } from "vitest";
import { render } from "@testing-library/react";

import { ViewerHeader } from "../ViewerHeader";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("../../chat/SaveToRepoButton", () => ({ SaveToRepoButton: () => <div data-testid="save" /> }));
vi.mock("../../report/ReportDownloadButton", () => ({ ReportDownloadButton: () => <div data-testid="report-dl" /> }));
vi.mock("../../chat/FileDownloadButton", () => ({ FileDownloadButton: () => <div data-testid="file-dl" /> }));

describe("ViewerHeader download affordance", () => {
  test("eu_v2_report renders the report download button + a standalone HTML link, but no file-dl", () => {
    const { queryByTestId, getByTestId, container } = render(
      <ViewerHeader
        filename="AAPL earnings"
        metadata="EU v2"
        source={{ kind: "eu_v2_report", reportId: "r1" }}
        onClose={() => undefined}
      />,
    );
    // sourceUrl must NOT be reached for eu_v2_report (no generic file download).
    expect(queryByTestId("file-dl")).toBeNull();
    // The EU download button (mocked ReportDownloadButton) renders.
    expect(getByTestId("report-dl")).toBeInTheDocument();
    // A standalone-HTML link pointing at the EU v2 html endpoint, opening
    // in a new tab.
    const standalone = container.querySelector(
      'a[href="/api/departments/earnings-update/v2/runs/r1/html"]',
    );
    expect(standalone).not.toBeNull();
    expect(standalone?.getAttribute("target")).toBe("_blank");
  });

  test("eu_v2_report with reportId + saveEngine=eu renders the Save-to-Repo button", () => {
    const { getByTestId } = render(
      <ViewerHeader
        filename="AAPL earnings"
        metadata="EU v2"
        source={{ kind: "eu_v2_report", reportId: "r1" }}
        reportId="r1"
        saveEngine="eu"
        onClose={() => undefined}
      />,
    );
    expect(getByTestId("save")).toBeInTheDocument();
    expect(getByTestId("report-dl")).toBeInTheDocument();
  });

  test("v3_report still renders a ReportDownloadButton", () => {
    const { getByTestId } = render(
      <ViewerHeader
        filename="f"
        metadata="m"
        source={{ kind: "v3_report", reportId: "r2" }}
        onClose={() => undefined}
      />,
    );
    expect(getByTestId("report-dl")).toBeInTheDocument();
  });
});
