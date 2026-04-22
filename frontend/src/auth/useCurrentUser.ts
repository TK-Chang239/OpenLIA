import { useAuth } from './AuthContext';

export interface CurrentUser {
  id: string;
  email: string | null;
  display_name: string | null;
  role: 'admin' | 'user';
  must_change_password: boolean;
}

export function useCurrentUser(): CurrentUser | null {
  const { user, mustChangePassword } = useAuth();
  if (!user) return null;
  return {
    id: user.id,
    email: user.email,
    display_name: user.display_name ?? null,
    role: user.role,
    must_change_password: mustChangePassword,
  };
}
