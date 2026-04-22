import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  getSession,
  login as loginRequest,
  logout as logoutRequest,
  type AuthUser,
  type LoginInput,
} from "../api/auth";
import { ApiError } from "../api/client";

export type AuthStatus =
  | "loading"
  | "authenticated"
  | "unauthenticated"
  | "personal";

export interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  mustChangePassword: boolean;
  login: (input: LoginInput) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  setMustChangePassword: (v: boolean) => void;
  clearMustChangePassword: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const LOCAL_USER: AuthUser = { id: "local", email: null, role: "admin" };

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps): JSX.Element {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [mustChangePassword, setMustChangePasswordState] =
    useState<boolean>(false);

  const refresh = useCallback(async (): Promise<void> => {
    try {
      const fetched = await getSession();
      setUser(fetched.user);
      setMustChangePasswordState(fetched.must_change_password);
      setStatus("authenticated");
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setUser(LOCAL_USER);
        setMustChangePasswordState(false);
        setStatus("personal");
        return;
      }
      setUser(null);
      setMustChangePasswordState(false);
      setStatus("unauthenticated");
    }
  }, []);

  const login = useCallback(async (input: LoginInput): Promise<void> => {
    const result = await loginRequest(input);
    setUser(result.user);
    setMustChangePasswordState(result.must_change_password);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    try {
      await logoutRequest();
    } catch (err) {
      console.warn("logout failed", err);
    }
    setUser(null);
    setMustChangePasswordState(false);
    setStatus("unauthenticated");
  }, []);

  const setMustChangePassword = useCallback((v: boolean) => {
    setMustChangePasswordState(v);
  }, []);

  const clearMustChangePassword = useCallback(() => {
    setMustChangePasswordState(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      mustChangePassword,
      login,
      logout,
      refresh,
      setMustChangePassword,
      clearMustChangePassword,
    }),
    [
      status,
      user,
      mustChangePassword,
      login,
      logout,
      refresh,
      setMustChangePassword,
      clearMustChangePassword,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}
