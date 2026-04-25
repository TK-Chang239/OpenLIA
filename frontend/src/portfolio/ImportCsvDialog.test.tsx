import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api/portfolio";
import { ImportCsvDialog } from "./ImportCsvDialog";

describe("ImportCsvDialog", () => {
  beforeEach(() => {
    vi.spyOn(api, "importCsv").mockResolvedValue({
      created: [],
      errors: [],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders nothing when closed", () => {
    const { container } = render(
      <ImportCsvDialog open={false} onClose={() => {}} onImported={() => {}} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("previews parsed rows", () => {
    render(
      <ImportCsvDialog open onClose={() => {}} onImported={() => {}} />,
    );
    fireEvent.change(screen.getByTestId("csv-text"), {
      target: { value: "ticker,shares\nAAPL,10\nMSFT,5\n" },
    });
    expect(screen.getByTestId("csv-preview")).toHaveTextContent("AAPL");
    expect(screen.getByTestId("csv-preview")).toHaveTextContent("MSFT");
  });

  it("submits and surfaces created/errors counts", async () => {
    vi.mocked(api.importCsv).mockResolvedValueOnce({
      created: [
        {
          id: "1",
          ticker: "AAPL",
          name: null,
          shares: null,
          cost_basis: null,
          currency: "USD",
          groups: [],
          notes_text: null,
          added_at: "",
          updated_at: "",
        },
      ],
      errors: [{ row: "2", error: "duplicate" }],
    });
    render(
      <ImportCsvDialog open onClose={() => {}} onImported={() => {}} />,
    );
    fireEvent.change(screen.getByTestId("csv-text"), {
      target: { value: "ticker\nAAPL\n" },
    });
    fireEvent.click(screen.getByTestId("csv-submit"));
    await waitFor(() => screen.getByTestId("csv-result"));
    expect(screen.getByTestId("csv-result")).toHaveTextContent(
      "Imported 1; 1 errors",
    );
  });
});
