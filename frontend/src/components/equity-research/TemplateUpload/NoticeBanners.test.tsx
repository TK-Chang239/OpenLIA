import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { NoticeBanners } from "./NoticeBanners";
import type { TemplateLoadNotice } from "../../../api/report-templates";

describe("NoticeBanners", () => {
  it("reserved-key notice renders yellow banner with key name", () => {
    const notices: TemplateLoadNotice[] = [
      { kind: "reserved_key", key: "extra_passes", message: "not supported in this engine version" },
    ];
    render(<NoticeBanners notices={notices} />);
    const banner = document.querySelector(".reserved-key-banner");
    expect(banner).not.toBeNull();
    expect(screen.getByText(/extra_passes/)).toBeInTheDocument();
    expect(screen.getByText(/not supported in this engine version/)).toBeInTheDocument();
  });

  it("unknown-key notice renders warning", () => {
    const notices: TemplateLoadNotice[] = [
      { kind: "unknown_key", key: "loops", message: "unrecognised key" },
    ];
    render(<NoticeBanners notices={notices} />);
    const banner = document.querySelector(".unknown-key-banner");
    expect(banner).not.toBeNull();
    expect(screen.getByText(/loops/)).toBeInTheDocument();
  });

  it("empty notices list renders nothing", () => {
    const { container } = render(<NoticeBanners notices={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
