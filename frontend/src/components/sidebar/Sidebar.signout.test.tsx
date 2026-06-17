import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const { mockState, mockLogout } = vi.hoisted(() => ({
  mockState: { status: "authenticated" as string },
  mockLogout: vi.fn(),
}));

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({
    status: mockState.status,
    user: { id: "u1", display_name: "Ada Admin", email: "ada@corp.com" },
    logout: mockLogout,
  }),
}));

vi.mock("./useNotificationPoll", () => ({
  useNotificationPoll: () => ({ unreadByDepartment: {}, markRead: vi.fn() }),
}));

import { Sidebar } from "./Sidebar";

function renderSidebar() {
  return render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  );
}

describe("Sidebar desktop sign-out", () => {
  it("shows the sign-out button when authenticated", () => {
    mockState.status = "authenticated";
    renderSidebar();
    expect(screen.getByRole("button", { name: /sign out/i })).toBeTruthy();
  });

  it("hides the sign-out button in personal mode", () => {
    mockState.status = "personal";
    renderSidebar();
    expect(screen.queryByRole("button", { name: /sign out/i })).toBeNull();
  });
});
