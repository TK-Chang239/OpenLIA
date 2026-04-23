import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { AttachmentChip } from "../AttachmentChip";
import { FileViewerProvider, useFileViewer } from "../../viewer/FileViewerContext";

function Probe() {
  const { current } = useFileViewer();
  return (
    <div data-testid="probe">{current ? `${current.filename}:${current.kind}` : "none"}</div>
  );
}

describe("AttachmentChip", () => {
  it("opens the file viewer context on click", () => {
    render(
      <FileViewerProvider>
        <Probe />
        <AttachmentChip
          filename="q.pdf"
          fileType="pdf"
          metadata="PDF · 248 KB"
          source={{ kind: "attachment", attachmentId: "7" }}
        />
      </FileViewerProvider>,
    );
    expect(screen.getByTestId("probe")).toHaveTextContent("none");
    fireEvent.click(screen.getByText("q.pdf"));
    expect(screen.getByTestId("probe")).toHaveTextContent("q.pdf:pdf");
  });

  it("does not open viewer when clicking the download button", () => {
    render(
      <FileViewerProvider>
        <Probe />
        <AttachmentChip
          filename="q.pdf"
          fileType="pdf"
          metadata="PDF"
          source={{ kind: "attachment", attachmentId: "7" }}
        />
      </FileViewerProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: /download/i }));
    expect(screen.getByTestId("probe")).toHaveTextContent("none");
  });
});
