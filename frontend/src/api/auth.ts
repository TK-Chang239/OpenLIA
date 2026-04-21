import { fetchJson } from "./client";

export interface AuthUser {
  id: string;
  email: string | null;
  role: "admin" | "user";
}

interface SessionResponse {
  user: AuthUser;
}

export async function getSession(): Promise<AuthUser> {
  const resp = await fetchJson<SessionResponse>("/api/auth/session");
  return resp.user;
}

export interface LoginInput {
  email: string;
  password: string;
  persistent: boolean;
}

export async function login(input: LoginInput): Promise<AuthUser> {
  const resp = await fetchJson<SessionResponse>("/api/auth/login", {
    method: "POST",
    json: input,
  });
  return resp.user;
}

export async function logout(): Promise<null> {
  return fetchJson<null>("/api/auth/logout", { method: "POST" });
}
