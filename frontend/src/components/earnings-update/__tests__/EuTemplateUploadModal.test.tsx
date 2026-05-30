import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EuTemplateUploadModal } from "../EuTemplateUploadModal";

describe("EuTemplateUploadModal", () => {
  it("renders when open", () => {
    render(<EuTemplateUploadModal open onClose={() => {}} onUpload={vi.fn()} />);
    expect(screen.getByText(/template/i)).toBeTruthy();
  });
});
