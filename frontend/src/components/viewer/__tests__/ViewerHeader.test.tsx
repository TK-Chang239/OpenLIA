import { describe, expect, test, vi } from "vitest";
import { render } from "@testing-library/react";

import { ViewerHeader } from "../ViewerHeader";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("../../chat/SaveToRepoButton", () => ({ SaveToRepoButton: () => <div data-testid="save" /> }));
vi.mock("../../report/ReportDownloadButton", () => ({ ReportDownloadButton: () => <div data-testid="report-dl" /> }));
vi.mock("../../chat/FileDownloadButton", () => ({ FileDownloadButton: () => <div data-testid="file-dl" /> }));

describe("ViewerHeader download affordance", () => {
  test("eu_v2_report renders without throwing and shows no download button (EU v2 is view-only)", () => {
    const { queryByTestId } = render(
      <ViewerHeader
        filename="AAPL earnings"
        metadata="EU v2"
        source={{ kind: "eu_v2_report", reportId: "r1" }}
        onClose={() => undefined}
      />,
    );
    expect(queryByTestId("file-dl")).toBeNull();
    expect(queryByTestId("report-dl")).toBeNull();
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
