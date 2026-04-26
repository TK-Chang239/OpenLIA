import "@testing-library/jest-dom";
import { afterEach } from "vitest";

// Wizard step components persist non-secret form fields to sessionStorage
// so back/forward navigation does not lose user input. Tests render those
// components multiple times in the same process — clear sessionStorage
// between tests so persisted state from one test does not leak into the
// next.
afterEach(() => {
  try {
    sessionStorage.clear();
  } catch {
    /* ignore environments without sessionStorage */
  }
});
