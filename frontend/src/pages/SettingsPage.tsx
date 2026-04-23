import { Navigate, Route, Routes } from 'react-router-dom';
import { SettingsShell } from '../components/settings/SettingsShell';
import { GeneralSection } from '../components/settings/sections/GeneralSection';
import { ModelsSection } from '../components/settings/sections/ModelsSection';
import { AccountSection } from '../components/settings/sections/AccountSection';
import { AdminSection } from '../components/settings/sections/AdminSection';
import { InvitesPanel } from '../components/settings/admin/InvitesPanel';
import { UsersPanel } from '../components/settings/admin/UsersPanel';
import { ResetRequestsPanel } from '../components/settings/admin/ResetRequestsPanel';
import { ModelsAdminPanel } from '../components/settings/admin/ModelsAdminPanel';
import { DataProvidersAdminPanel } from '../components/settings/admin/DataProvidersAdminPanel';
import { useCurrentUser } from '../auth/useCurrentUser';

export function SettingsPage(): JSX.Element {
  const user = useCurrentUser();
  if (!user) return <p className="p-6 text-text-secondary">Loading...</p>;
  const isAdmin = user.role === 'admin';
  return (
    <Routes>
      <Route element={<SettingsShell userRole={user.role} />}>
        <Route index element={<Navigate to="general" replace />} />
        <Route path="general" element={<GeneralSection />} />
        <Route path="models" element={<ModelsSection />} />
        <Route
          path="account"
          element={
            <AccountSection
              currentEmail={user.email ?? ''}
              mustChangePassword={user.must_change_password}
            />
          }
        />
        {isAdmin ? (
          <Route path="admin" element={<AdminSection />}>
            <Route index element={<Navigate to="invites" replace />} />
            <Route path="invites" element={<InvitesPanel />} />
            <Route path="users" element={<UsersPanel currentUserId={user.id} />} />
            <Route path="reset-requests" element={<ResetRequestsPanel />} />
            <Route path="models" element={<ModelsAdminPanel />} />
            <Route path="data-providers" element={<DataProvidersAdminPanel />} />
          </Route>
        ) : null}
        <Route path="*" element={<Navigate to="general" replace />} />
      </Route>
    </Routes>
  );
}
