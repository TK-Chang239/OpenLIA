import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("pdfjs-dist", () => ({
  getDocument: () => ({ promise: Promise.resolve({ numPages: 0, getPage: vi.fn() }) }),
  GlobalWorkerOptions: { workerSrc: "" },
}));

vi.mock("framer-motion", async (importOriginal) => {
  const actual = await importOriginal<typeof import("framer-motion")>();
  type AnyProps = Record<string, unknown> & { children?: React.ReactNode };
  const stripFmProps = (props: AnyProps) => {
    const {
      initial: _i,
      animate: _a,
      exit: _e,
      transition: _t,
      whileHover: _w,
      ...rest
    } = props;
    return rest;
  };
  return {
    ...actual,
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    motion: {
      ...actual.motion,
      aside: ({ children, ...props }: AnyProps) => (
        <aside {...stripFmProps(props)}>{children}</aside>
      ),
      div: ({ children, ...props }: AnyProps) => (
        <div {...stripFmProps(props)}>{children}</div>
      ),
      button: ({ children, ...props }: AnyProps) => (
        <button {...stripFmProps(props)}>{children}</button>
      ),
    },
    useReducedMotion: () => false,
  };
});
import { FileViewer } from "../FileViewer";
import { FileViewerProvider, useFileViewer } from "../FileViewerContext";

function Trigger() {
  const { open } = useFileViewer();
  return (
    <button
      onClick={() =>
        open({
          filename: "q.pdf",
          kind: "pdf",
          metadata: "PDF · 12 pages",
          source: { kind: "report", reportId: "5" },
        })
      }
    >
      open
    </button>
  );
}

describe("FileViewer", () => {
  it("renders nothing when no file is open", () => {
    const { container } = render(
      <FileViewerProvider>
        <Trigger />
        <FileViewer />
      </FileViewerProvider>,
    );
    expect(container.querySelector('[role="complementary"]')).toBeNull();
  });

  it("renders panel with filename + metadata after opening", () => {
    render(
      <FileViewerProvider>
        <Trigger />
        <FileViewer />
      </FileViewerProvider>,
    );
    fireEvent.click(screen.getByText("open"));
    expect(screen.getByText("q.pdf")).toBeInTheDocument();
    expect(screen.getByText("PDF · 12 pages")).toBeInTheDocument();
  });

  it("closes when the close button is clicked", async () => {
    const { container } = render(
      <FileViewerProvider>
        <Trigger />
        <FileViewer />
      </FileViewerProvider>,
    );
    fireEvent.click(screen.getByText("open"));
    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    await waitFor(() => expect(container.querySelector('[role="complementary"]')).toBeNull());
  });

  it("closes on Escape", async () => {
    const { container } = render(
      <FileViewerProvider>
        <Trigger />
        <FileViewer />
      </FileViewerProvider>,
    );
    fireEvent.click(screen.getByText("open"));
    fireEvent.keyDown(screen.getByRole("complementary"), { key: "Escape" });
    await waitFor(() => expect(container.querySelector('[role="complementary"]')).toBeNull());
  });
});
