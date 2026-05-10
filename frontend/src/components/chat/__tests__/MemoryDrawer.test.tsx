import { useState } from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryDrawer, MemoryDrawerToggle } from "../MemoryDrawer";
import * as graphApi from "../../../api/graph";

const BASE_PROPOSAL = {
  id: "p1",
  kind: "user_construct",
  status: "pending" as const,
  created_at: "2026-05-10T00:00:00Z",
};

describe("MemoryDrawer", () => {
  beforeEach(() => {
    vi.spyOn(graphApi, "listProposals").mockResolvedValue({ items: [] });
  });

  it("renders the injected memory block when supplied", async () => {
    render(
      <MemoryDrawer
        open
        onClose={() => {}}
        memoryBlock={"## Memory\n- NVDA: services-margin thesis"}
      />,
    );
    await waitFor(() =>
      expect(graphApi.listProposals).toHaveBeenCalledWith("pending"),
    );
    const content = screen.getByTestId("memory-block-content");
    expect(content.textContent).toContain("NVDA");
    expect(content.textContent).toContain("services-margin");
  });

  it("renders the empty state when block is null", async () => {
    render(
      <MemoryDrawer open onClose={() => {}} memoryBlock={null} />,
    );
    await waitFor(() => screen.getByTestId("memory-block-empty"));
    expect(
      screen.getByTestId("memory-block-empty").textContent,
    ).toMatch(/no memory injected/i);
  });

  it("renders the pending state when no event has arrived yet", async () => {
    render(
      <MemoryDrawer open onClose={() => {}} memoryBlock={undefined} />,
    );
    await waitFor(() => screen.getByTestId("memory-block-pending"));
  });

  it("renders the pending proposals list when proposals exist", async () => {
    vi.spyOn(graphApi, "listProposals").mockResolvedValue({
      items: [
        {
          ...BASE_PROPOSAL,
          id: "p1",
          payload: {
            statement: "User holds 100 shares of NVDA",
            entity_value: "NVDA",
          },
        },
        {
          ...BASE_PROPOSAL,
          id: "p2",
          payload: {
            statement: "User is bearish on TSLA into earnings",
            entity_value: "TSLA",
          },
        },
      ],
    });
    render(
      <MemoryDrawer open onClose={() => {}} memoryBlock={null} />,
    );
    await waitFor(() => screen.getByText(/User holds 100 shares of NVDA/));
    expect(screen.getByText(/User is bearish on TSLA/)).toBeInTheDocument();
    expect(screen.getAllByTestId("memory-proposal-row")).toHaveLength(2);
  });

  it("renders the empty-proposals state when none are pending", async () => {
    render(
      <MemoryDrawer open onClose={() => {}} memoryBlock={null} />,
    );
    await waitFor(() => screen.getByTestId("memory-proposals-empty"));
  });

  it("accept/dismiss buttons call the API and remove the row", async () => {
    vi.spyOn(graphApi, "listProposals").mockResolvedValue({
      items: [
        {
          ...BASE_PROPOSAL,
          id: "p1",
          payload: { statement: "Accept me", entity_value: "AAPL" },
        },
        {
          ...BASE_PROPOSAL,
          id: "p2",
          payload: { statement: "Dismiss me", entity_value: "MSFT" },
        },
      ],
    });
    const accept = vi
      .spyOn(graphApi, "acceptProposal")
      .mockResolvedValue({
        id: "c1",
        kind: "thesis",
        status: "confirmed",
        statement: "Accept me",
        entity_id: "e1",
        created_at: "2026-05-10T00:00:00Z",
        updated_at: "2026-05-10T00:00:00Z",
      });
    const dismiss = vi
      .spyOn(graphApi, "dismissProposal")
      .mockResolvedValue({ ok: true });

    render(<MemoryDrawer open onClose={() => {}} memoryBlock={null} />);
    await waitFor(() => screen.getByText("Accept me"));

    fireEvent.click(screen.getAllByRole("button", { name: /^Accept$/ })[0]);
    await waitFor(() => expect(accept).toHaveBeenCalledWith("p1"));
    await waitFor(() =>
      expect(screen.queryByText("Accept me")).not.toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: /^Dismiss$/ }));
    await waitFor(() => expect(dismiss).toHaveBeenCalledWith("p2"));
    await waitFor(() =>
      expect(screen.queryByText("Dismiss me")).not.toBeInTheDocument(),
    );
  });

  it("renders nothing when open is false", () => {
    const { container } = render(
      <MemoryDrawer open={false} onClose={() => {}} memoryBlock={"x"} />,
    );
    expect(container.firstChild).toBeNull();
  });
});

describe("MemoryDrawerToggle", () => {
  beforeEach(() => {
    vi.spyOn(graphApi, "listProposals").mockResolvedValue({ items: [] });
  });

  function Harness() {
    const [open, setOpen] = useState(false);
    return (
      <>
        <MemoryDrawerToggle open={open} onClick={() => setOpen((v) => !v)} />
        <MemoryDrawer
          open={open}
          onClose={() => setOpen(false)}
          memoryBlock={null}
        />
      </>
    );
  }

  it("toggles the drawer open and closed", async () => {
    render(<Harness />);
    const btn = screen.getByRole("button", { name: /toggle memory drawer/i });
    expect(btn).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(btn);
    await waitFor(() => screen.getByTestId("memory-drawer"));
    expect(btn).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(btn);
    await waitFor(() =>
      expect(screen.queryByTestId("memory-drawer")).not.toBeInTheDocument(),
    );
  });
});
