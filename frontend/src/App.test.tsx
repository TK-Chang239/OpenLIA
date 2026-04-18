import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import App from "./App";

describe("App", () => {
  it("renders the OpenLIA heading", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /openlia/i })).toBeInTheDocument();
  });
});
