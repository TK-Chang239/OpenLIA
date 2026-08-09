import { fetchJson } from "./client";

export interface AuthUser {
  id: string;
  email: string | null;
  display_name?: string | null;
  role: "admin" | "user";
}

interface BackendUser {
  user_id: string;
  email: string | null;
  display_name?: string | null;
  is_admin?: boolean;
  must_change_password?: boolean;
}

interface BackendLoginResponse extends BackendUser {
  must_change_password?: boolean;
}

function toAuthUser(raw: BackendUser): AuthUser {
  return {
    id: raw.user_id,
    email: raw.email,
    display_name: raw.display_name ?? null,
    role: raw.is_admin ? "admin" : "user",
  };
}

export interface SessionResult {
  user: AuthUser;
  must_change_password: boolean;
}

export async function getSession(): Promise<SessionResult> {
  const resp = await fetchJson<BackendUser>("/api/auth/session");
  return {
    user: toAuthUser(resp),
    must_change_password: Boolean(resp.must_change_password),
  };
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
  const resp = await fetchJson<BackendLoginResponse>("/api/auth/login", {
    method: "POST",
    json: input,
  });
  return {
    user: toAuthUser(resp),
    must_change_password: Boolean(resp.must_change_password),
  };
}

export async function logout(): Promise<null> {
  return fetchJson<null>("/api/auth/logout", { method: "POST" });
}

export async function logoutAll(): Promise<null> {
  return fetchJson<null>("/api/auth/logout-all", { method: "POST" });
}

export interface AuthSession {
  id: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  user_agent: string | null;
  ip_address: string | null;
  current: boolean;
}

export async function listAuthSessions(): Promise<AuthSession[]> {
  const resp = await fetchJson<{ sessions: AuthSession[] }>(
    "/api/auth/sessions",
  );
  return resp.sessions;
}

export async function revokeAuthSession(id: string): Promise<void> {
  await fetchJson<void>(`/api/auth/sessions/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export interface RegisterInput {
  email: string;
  password: string;
  display_name?: string;
  invite_token: string;
}

export async function register(input: RegisterInput): Promise<LoginResult> {
  const resp = await fetchJson<BackendLoginResponse>("/api/auth/register", {
    method: "POST",
    json: input,
  });
  return {
    user: toAuthUser(resp),
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
