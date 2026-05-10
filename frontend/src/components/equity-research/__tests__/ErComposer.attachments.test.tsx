import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { ErComposer } from "../ErComposer";

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

function _renderComposer(onSubmit = vi.fn()) {
  render(
    <ErComposer
      value=""
      onChange={() => {}}
      onSubmit={onSubmit}
      isStreaming={false}
      placeholder="Ask"
      mode="stock_initiation"
      length="normal"
      onModeClick={() => {}}
    />,
  );
  return onSubmit;
}

describe("ErComposer attachments", () => {
  it("accepts a supported text file and forwards it to onSubmit", () => {
    const onSubmit = _renderComposer();
    const input = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;

    const f = _file("notes.txt", "hello", "text/plain");
    _selectFiles(input, [f]);

    expect(screen.getByText("notes.txt")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Send"));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][1]).toEqual([f]);
  });

  it("rejects a disallowed mime with a visible error", () => {
    _renderComposer();
    const input = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    _selectFiles(input, [_file("evil.zip", "PK", "application/zip")]);

    expect(screen.queryByText("evil.zip")).not.toBeInTheDocument();
    expect(screen.getByRole("alert").textContent).toMatch(/evil\.zip/);
  });

  it("rejects oversized files", () => {
    _renderComposer();
    const input = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    _selectFiles(input, [_file("huge.txt", "x", "text/plain", 26 * 1024 * 1024)]);

    expect(screen.getByRole("alert").textContent).toMatch(/too large/i);
  });

  it("caps at 10 files and surfaces an error", () => {
    _renderComposer();
    const input = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const files = Array.from({ length: 12 }, (_, i) =>
      _file(`f${i}.txt`, "x", "text/plain"),
    );
    _selectFiles(input, files);

    expect(screen.queryByText("f10.txt")).not.toBeInTheDocument();
    expect(screen.getByRole("alert").textContent).toMatch(/10 files/);
  });

  it("clears attachments and errors after send", () => {
    const onSubmit = _renderComposer();
    const input = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    _selectFiles(input, [_file("a.txt", "x", "text/plain")]);
    fireEvent.click(screen.getByLabelText("Send"));

    expect(screen.queryByText("a.txt")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(onSubmit).toHaveBeenCalled();
  });
});
