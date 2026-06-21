import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { SettingsPage } from './SettingsPage';

const mocks = vi.hoisted(() => ({ role: 'admin' as 'admin' | 'user' }));

vi.mock('../auth/useCurrentUser', () => ({
  useCurrentUser: () => ({
    id: '00000000-0000-4000-8000-000000000001',
    email: 'alice@x.io',
    role: mocks.role,
    display_name: 'Alice',
    must_change_password: false,
  }),
}));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ status: 'personal' }),
}));

vi.mock('../components/settings/sections/GeneralSection', () => ({
  GeneralSection: () => <h1>General</h1>,
}));
vi.mock('../components/settings/sections/ModelsSection', () => ({
  ModelsSection: () => <h1>Models</h1>,
}));
vi.mock('../components/settings/sections/ConnectorsSection', () => ({
  ConnectorsSection: () => <h1>Connectors</h1>,
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

function renderAt(path: string) {
  const router = createMemoryRouter(
    [{ path: '/settings/*', element: <SettingsPage /> }],
    { initialEntries: [path] },
  );
  return render(<RouterProvider router={router} />);
}

describe('SettingsPage', () => {
  beforeEach(() => {
    mocks.role = 'admin';
  });

  it('renders General section at /settings/general', async () => {
    renderAt('/settings/general');
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /^General$/ })).toBeInTheDocument(),
    );
  });

  it('renders Connectors at /settings/connectors for an admin', async () => {
    mocks.role = 'admin';
    renderAt('/settings/connectors');
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /^Connectors$/ })).toBeInTheDocument(),
    );
  });

  it('hides Connectors from a non-admin (no tab, ConnectorsSection never mounts)', async () => {
    mocks.role = 'user';
    renderAt('/settings/general');
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /^General$/ })).toBeInTheDocument(),
    );
    // Models tab stays visible to all; the admin-only Connectors tab is hidden,
    // so a non-admin can't reach ConnectorsSection (which fetches the
    // admin-only /api/connectors and would 403).
    expect(screen.getByRole('link', { name: /^Models$/ })).toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: /connectors/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: /^Connectors$/ }),
    ).not.toBeInTheDocument();
  });
});
