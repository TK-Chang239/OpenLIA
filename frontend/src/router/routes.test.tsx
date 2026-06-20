import { describe, it, expect } from "vitest";
import type { ReactElement } from "react";
import type { RouteObject } from "react-router-dom";
import { routes } from "./routes";
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";
import { ForgotPasswordPage } from "../pages/ForgotPasswordPage";
import { ResetPasswordPage } from "../pages/ResetPasswordPage";

function findByPath(rs: RouteObject[], path: string): RouteObject | undefined {
  for (const r of rs) {
    if (r.path === path) return r;
    if (r.children) {
      const found = findByPath(r.children, path);
      if (found) return found;
    }
  }
  return undefined;
}

describe("auth routes are enabled", () => {
  it.each([
    ["/login", LoginPage],
    ["/register", RegisterPage],
    ["/forgot-password", ForgotPasswordPage],
    ["/reset-password", ResetPasswordPage],
  ])("%s renders its real page element", (path, Page) => {
    const route = findByPath(routes, path as string);
    expect(route).toBeTruthy();
    const element = route!.element as ReactElement;
    expect(element.type).toBe(Page);
  });
});
