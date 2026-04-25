import { describe, expect, it } from "vitest";
import { ApiError } from "./client";
import { mapTransportError } from "./errors";

describe("mapTransportError", () => {
  it("maps native TypeError to offline message", () => {
    const out = mapTransportError(new TypeError("Failed to fetch"));
    expect(out.message).toMatch(/Can't reach the server/);
    expect(out.variant).toBe("error");
  });

  it("maps ApiError(0) to offline message", () => {
    const out = mapTransportError(new ApiError(0, "network error"));
    expect(out.message).toMatch(/Can't reach the server/);
  });

  it("maps 500 ApiError to server-error message", () => {
    const out = mapTransportError(new ApiError(500, "boom"));
    expect(out.message).toMatch(/Something went wrong on our end/);
    expect(out.variant).toBe("error");
  });

  it("maps 502 ApiError to server-error message", () => {
    const out = mapTransportError(new ApiError(502, "bad gateway"));
    expect(out.message).toMatch(/Something went wrong on our end/);
  });

  it("falls back to unknown for 4xx ApiError", () => {
    const out = mapTransportError(new ApiError(400, "bad request"));
    expect(out.message).toMatch(/Unexpected error/);
  });

  it("falls back to unknown for non-Error objects", () => {
    const out = mapTransportError({ weird: true });
    expect(out.message).toMatch(/Unexpected error/);
  });
});
