import { describe, it, expect } from "vitest";
import { parsePipCommand } from "../parsePipCommand";

describe("parsePipCommand", () => {
  it("returns an error when no 'install' token is present", () => {
    const result = parsePipCommand("pip uninstall eodhd");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toMatch(/install/i);
    }
  });

  it("returns an error when no package name follows 'install'", () => {
    const result = parsePipCommand("pip install");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toMatch(/package/i);
    }
  });

  it("extracts the package name from a plain `pip install <pkg>` command", () => {
    const result = parsePipCommand("pip install eodhd");
    expect(result).toEqual({
      ok: true,
      pipName: "eodhd",
      pipVersion: "",
      importModule: "eodhd",
    });
  });

  it("ignores the -U / --upgrade flag", () => {
    const result = parsePipCommand("pip install eodhd -U");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.pipName).toBe("eodhd");
    }
  });

  it("handles the `python3 -m pip install <pkg>` form", () => {
    const result = parsePipCommand("python3 -m pip install eodhd -U");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.pipName).toBe("eodhd");
      expect(result.importModule).toBe("eodhd");
    }
  });

  it("extracts the pinned version from `pkg==1.2.3`", () => {
    const result = parsePipCommand("pip install eodhd==1.2.3");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.pipName).toBe("eodhd");
      expect(result.pipVersion).toBe("==1.2.3");
    }
  });

  it("extracts the version spec from `pkg>=2.0`", () => {
    const result = parsePipCommand("pip install 'eodhd>=2.0'");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.pipName).toBe("eodhd");
      expect(result.pipVersion).toBe(">=2.0");
    }
  });

  it("converts hyphenated package names to underscored import module guesses", () => {
    const result = parsePipCommand("pip install some-sdk");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.pipName).toBe("some-sdk");
      expect(result.importModule).toBe("some_sdk");
    }
  });
});
