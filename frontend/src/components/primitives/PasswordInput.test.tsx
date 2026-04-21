import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PasswordInput } from "./PasswordInput";

describe("PasswordInput", () => {
  it("renders masked by default", () => {
    render(
      <PasswordInput id="pw" value="hunter2" onChange={() => undefined} />,
    );
    const input = screen.getByTestId("password-input") as HTMLInputElement;
    expect(input.type).toBe("password");
  });

  it("toggles to text when show/hide pressed", () => {
    render(
      <PasswordInput id="pw" value="hunter2" onChange={() => undefined} />,
    );
    const toggle = screen.getByRole("button", { name: /show password/i });
    fireEvent.click(toggle);
    const input = screen.getByTestId("password-input") as HTMLInputElement;
    expect(input.type).toBe("text");
    const toggleAgain = screen.getByRole("button", { name: /hide password/i });
    fireEvent.click(toggleAgain);
    expect((screen.getByTestId("password-input") as HTMLInputElement).type).toBe(
      "password",
    );
  });

  it("forwards onChange with the new string value", () => {
    const handle = vi.fn();
    render(<PasswordInput id="pw" value="" onChange={handle} />);
    const input = screen.getByTestId("password-input");
    fireEvent.change(input, { target: { value: "abc" } });
    expect(handle).toHaveBeenCalledWith("abc");
  });
});
