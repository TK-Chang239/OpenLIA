import { describe, it, expect } from "vitest";
import { passwordStrength } from "./passwordStrength";

describe("passwordStrength", () => {
  it("returns 0 for empty input", () => {
    expect(passwordStrength("")).toBe(0);
  });

  it("returns 1 for < 8 chars regardless of class mix", () => {
    expect(passwordStrength("aB1!")).toBe(1);
    expect(passwordStrength("abc")).toBe(1);
  });

  it("returns 2 for 8+ chars with 2 character classes", () => {
    expect(passwordStrength("abcdefgh")).toBe(2);       // 1 class → still 2 (length carries)
    expect(passwordStrength("abcdefgH")).toBe(2);       // 2 classes
    expect(passwordStrength("abcdefg1")).toBe(2);       // 2 classes
  });

  it("returns 3 for 8+ chars with 3 classes", () => {
    expect(passwordStrength("Abcdefg1")).toBe(3);
  });

  it("returns 4 for 8+ chars with 4 classes", () => {
    expect(passwordStrength("Abcdefg1!")).toBe(4);
  });
});
