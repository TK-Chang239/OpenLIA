import { fetchJson } from "./client";

export interface AuthUser {
  id: string;
  email: string | null;
  display_name?: string | null;
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

export interface LoginResult {
  user: AuthUser;
  must_change_password: boolean;
}

export async function login(input: LoginInput): Promise<LoginResult> {
  const resp = await fetchJson<{
    user: AuthUser;
    must_change_password?: boolean;
  }>("/api/auth/login", {
    method: "POST",
    json: input,
  });
  return {
    user: resp.user,
    must_change_password: Boolean(resp.must_change_password),
  };
}

export async function logout(): Promise<null> {
  return fetchJson<null>("/api/auth/logout", { method: "POST" });
}

export async function logoutAll(): Promise<null> {
  return fetchJson<null>("/api/auth/logout-all", { method: "POST" });
}

export interface RegisterInput {
  email: string;
  password: string;
  display_name?: string;
  invite_token: string;
}

export async function register(input: RegisterInput): Promise<LoginResult> {
  const resp = await fetchJson<{
    user: AuthUser;
    must_change_password?: boolean;
  }>("/api/auth/register", {
    method: "POST",
    json: input,
  });
  return {
    user: resp.user,
    must_change_password: Boolean(resp.must_change_password),
  };
}

export interface SignupPolicy {
  mode: "invite_only" | "closed" | "open";
  invite_required: boolean;
}

export async function getSignupPolicy(): Promise<SignupPolicy> {
  return fetchJson<SignupPolicy>("/api/auth/signup-policy");
}

export async function requestPasswordReset(email: string): Promise<null> {
  return fetchJson<null>("/api/auth/password-reset/request", {
    method: "POST",
    json: { email },
  });
}

export interface ConsumePasswordResetInput {
  token: string;
  new_password: string;
}

export async function consumePasswordReset(
  input: ConsumePasswordResetInput,
): Promise<null> {
  return fetchJson<null>("/api/auth/password-reset/consume", {
    method: "POST",
    json: input,
  });
}

export interface ChangePasswordInput {
  current_password: string;
  new_password: string;
}

export async function changePassword(
  input: ChangePasswordInput,
): Promise<null> {
  return fetchJson<null>("/api/auth/change-password", {
    method: "POST",
    json: input,
  });
}
