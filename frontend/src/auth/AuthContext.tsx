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
  login: (input: LoginInput) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const LOCAL_USER: AuthUser = { id: "local", email: null, role: "admin" };

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps): JSX.Element {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);

  const refresh = useCallback(async (): Promise<void> => {
    try {
      const fetched = await getSession();
      setUser(fetched);
      setStatus("authenticated");
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setUser(LOCAL_USER);
        setStatus("personal");
        return;
      }
      setUser(null);
      setStatus("unauthenticated");
    }
  }, []);

  const login = useCallback(
    async (input: LoginInput): Promise<void> => {
      const fetched = await loginRequest(input);
      setUser(fetched);
      setStatus("authenticated");
    },
    [],
  );

  const logout = useCallback(async (): Promise<void> => {
    await logoutRequest();
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, login, logout, refresh }),
    [status, user, login, logout, refresh],
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
