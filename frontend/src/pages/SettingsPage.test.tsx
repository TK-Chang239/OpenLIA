import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { SettingsPage } from './SettingsPage';

vi.mock('../auth/useCurrentUser', () => ({
  useCurrentUser: () => ({
    id: '00000000-0000-4000-8000-000000000001',
    email: 'alice@x.io',
    role: 'admin',
    display_name: 'Alice',
    must_change_password: false,
  }),
}));

vi.mock('../components/settings/sections/GeneralSection', () => ({
  GeneralSection: () => <h1>General</h1>,
}));
vi.mock('../components/settings/sections/ModelsSection', () => ({
  ModelsSection: () => <h1>Models</h1>,
}));
vi.mock('../components/settings/sections/AccountSection', () => ({
  AccountSection: () => <h1>Account</h1>,
}));
vi.mock('../components/settings/sections/AdminSection', () => ({
  AdminSection: () => <h1>Admin</h1>,
}));
vi.mock('../components/settings/admin/InvitesPanel', () => ({
  InvitesPanel: () => null,
}));
vi.mock('../components/settings/admin/UsersPanel', () => ({
  UsersPanel: () => null,
}));
vi.mock('../components/settings/admin/ResetRequestsPanel', () => ({
  ResetRequestsPanel: () => null,
}));
vi.mock('../components/settings/admin/ModelsAdminPanel', () => ({
  ModelsAdminPanel: () => null,
}));
vi.mock('../components/settings/admin/DataProvidersAdminPanel', () => ({
  DataProvidersAdminPanel: () => null,
}));

describe('SettingsPage', () => {
  it('redirects /settings to /settings/general', async () => {
    render(
      <MemoryRouter initialEntries={['/settings']}>
        <Routes>
          <Route path="/settings/*" element={<SettingsPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByRole('heading', { name: /general/i })).toBeInTheDocument());
  });
});
