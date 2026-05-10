import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { ChatInput } from "../ChatInput";

function _file(name: string, body: string, mime: string, sizeBytes?: number): File {
  const f = new File([body], name, { type: mime });
  if (sizeBytes && sizeBytes !== body.length) {
    Object.defineProperty(f, "size", { value: sizeBytes });
  }
  return f;
}

function _selectFiles(input: HTMLInputElement, files: File[]) {
  Object.defineProperty(input, "files", {
    value: files,
    configurable: true,
  });
  fireEvent.change(input);
}

describe("ChatInput attachments", () => {
  it("accepts a supported text file and forwards it to onSend", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} isStreaming={false} placeholder="Ask" />);
    const input = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;

    const f = _file("notes.txt", "hello", "text/plain");
    _selectFiles(input, [f]);

    expect(screen.getByText("notes.txt")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Send"));

    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend.mock.calls[0][0]).toBe("");
    expect(onSend.mock.calls[0][1]).toEqual([f]);
  });

  it("rejects a disallowed mime with a visible error and does not attach", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} isStreaming={false} placeholder="Ask" />);
    const input = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;

    const bad = _file("evil.zip", "PK", "application/zip");
    _selectFiles(input, [bad]);

    expect(screen.queryByText("evil.zip")).not.toBeInTheDocument();
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(/evil\.zip/);
    expect(alert.textContent?.toLowerCase()).toMatch(/not supported/);
  });

  it("rejects oversized files with a clear error", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} isStreaming={false} placeholder="Ask" />);
    const input = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;

    const big = _file("huge.txt", "x", "text/plain", 26 * 1024 * 1024);
    _selectFiles(input, [big]);

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(/huge\.txt/);
    expect(alert.textContent?.toLowerCase()).toMatch(/too large/);
  });

  it("caps at 10 files per message and surfaces an error", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} isStreaming={false} placeholder="Ask" />);
    const input = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;

    const files = Array.from({ length: 12 }, (_, i) =>
      _file(`f${i}.txt`, "x", "text/plain"),
    );
    _selectFiles(input, files);

    expect(screen.getByText("f0.txt")).toBeInTheDocument();
    expect(screen.getByText("f9.txt")).toBeInTheDocument();
    expect(screen.queryByText("f10.txt")).not.toBeInTheDocument();
    expect(screen.getByRole("alert").textContent).toMatch(/10 files/);
  });

  it("sending clears the attachments and the error chip", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} isStreaming={false} placeholder="Ask" />);
    const input = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;

    _selectFiles(input, [_file("a.txt", "x", "text/plain")]);
    fireEvent.click(screen.getByLabelText("Send"));

    expect(screen.queryByText("a.txt")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
