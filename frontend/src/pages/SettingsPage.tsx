import { Navigate, Route, Routes } from 'react-router-dom';
import { SettingsShell } from '../components/settings/SettingsShell';
import { GeneralSection } from '../components/settings/sections/GeneralSection';
import { ModelsSection } from '../components/settings/sections/ModelsSection';
import { TimezoneSection } from '../components/settings/sections/TimezoneSection';
import { AccountSection } from '../components/settings/sections/AccountSection';
import { AdminSection } from '../components/settings/sections/AdminSection';
import { DisclaimerSection } from '../components/settings/sections/DisclaimerSection';
import { GuardrailActivitySection } from '../components/settings/sections/GuardrailActivitySection';
import { SkillsSection } from '../components/settings/sections/SkillsSection';
import { CustomTemplatesSection } from '../components/settings/sections/CustomTemplatesSection';
import { CacheAdmin } from '../components/equity-research/CacheAdmin/CacheAdmin';
import { AdminSkillsSection } from '../components/settings/sections/AdminSkillsSection';
import { InvitesPanel } from '../components/settings/admin/InvitesPanel';
import { UsersPanel } from '../components/settings/admin/UsersPanel';
import { ResetRequestsPanel } from '../components/settings/admin/ResetRequestsPanel';
import { ConnectorsSection } from '../components/settings/sections/ConnectorsSection';
import { useCurrentUser } from '../auth/useCurrentUser';
import { useAuth } from '../auth/AuthContext';

export function SettingsPage(): JSX.Element {
  const user = useCurrentUser();
  const { status } = useAuth();
  if (!user) return <p className="p-6 text-text-secondary">Loading...</p>;
  const isAdmin = user.role === 'admin';
  const mode: 'personal' | 'company' = status === 'personal' ? 'personal' : 'company';
  return (
    <Routes>
      <Route element={<SettingsShell userRole={user.role} />}>
        <Route index element={<Navigate to="general" replace />} />
        <Route path="general" element={<GeneralSection />} />
        <Route path="models" element={<ModelsSection userRole={user.role} />} />
        {isAdmin ? (
          <Route path="connectors" element={<ConnectorsSection />} />
        ) : null}
        <Route path="timezone" element={<TimezoneSection />} />
        <Route
          path="account"
          element={
            <AccountSection
              currentEmail={user.email ?? ''}
              mustChangePassword={user.must_change_password}
            />
          }
        />
        <Route path="disclaimer" element={<DisclaimerSection mode={mode} />} />
        <Route path="guardrails" element={<GuardrailActivitySection mode={mode} />} />
        <Route path="skills" element={<SkillsSection />} />
        <Route path="report-templates" element={<CustomTemplatesSection />} />
        <Route path="cache" element={<CacheAdmin />} />
        {isAdmin ? (
          <Route path="admin" element={<AdminSection />}>
            <Route index element={<Navigate to="invites" replace />} />
            <Route path="invites" element={<InvitesPanel />} />
            <Route path="users" element={<UsersPanel currentUserId={user.id} />} />
            <Route path="reset-requests" element={<ResetRequestsPanel />} />
            <Route path="skills" element={<AdminSkillsSection />} />
          </Route>
        ) : null}
        <Route path="*" element={<Navigate to="general" replace />} />
      </Route>
    </Routes>
  );
}
