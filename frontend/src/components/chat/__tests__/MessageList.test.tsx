import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MessageList } from "../MessageList";

describe("MessageList", () => {
  it("renders children", () => {
    render(
      <MessageList>
        <div>first</div>
        <div>second</div>
      </MessageList>,
    );
    expect(screen.getByText("first")).toBeInTheDocument();
    expect(screen.getByText("second")).toBeInTheDocument();
  });

  it("has max-w-[720px] column", () => {
    render(<MessageList><div>x</div></MessageList>);
    expect(screen.getByTestId("message-column").className).toMatch(/max-w-\[720px\]/);
  });
});
