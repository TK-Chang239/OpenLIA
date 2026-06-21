import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { SettingsPage } from '../SettingsPage';

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ status: 'personal' }),
}));

vi.mock('../../components/settings/sections/GeneralSection', () => ({
  GeneralSection: () => <p>general body</p>,
}));
vi.mock('../../components/settings/sections/ModelsSection', () => ({
  ModelsSection: () => <p>models body</p>,
}));
vi.mock('../../components/settings/sections/AccountSection', () => ({
  AccountSection: () => <p>account body</p>,
}));
vi.mock('../../components/settings/sections/AdminSection', () => ({
  AdminSection: () => <p>admin body</p>,
}));
vi.mock('../../components/settings/admin/InvitesPanel', () => ({
  InvitesPanel: () => <p>invites body</p>,
}));
vi.mock('../../components/settings/admin/UsersPanel', () => ({
  UsersPanel: () => <p>users body</p>,
}));
vi.mock('../../components/settings/admin/ResetRequestsPanel', () => ({
  ResetRequestsPanel: () => <p>resets body</p>,
}));
vi.mock('../../components/settings/sections/ConnectorsSection', () => ({
  ConnectorsSection: () => <p>connectors body</p>,
}));

import * as currentUserModule from '../../auth/useCurrentUser';

function renderAt(path: string) {
  const router = createMemoryRouter(
    [{ path: '/settings/*', element: <SettingsPage /> }],
    { initialEntries: [path] },
  );
  return render(<RouterProvider router={router} />);
}

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('shows Admin tab when user is admin', async () => {
    vi.spyOn(currentUserModule, 'useCurrentUser').mockReturnValue({
      id: 'u-admin',
      email: 'admin@example.com',
      display_name: 'Admin',
      role: 'admin',
      must_change_password: false,
    });
    renderAt('/settings/general');
    await waitFor(() => screen.getByText('general body'));
    expect(screen.getByRole('link', { name: /admin/i })).toBeInTheDocument();
  });

  it('hides Admin tab for non-admin users', async () => {
    vi.spyOn(currentUserModule, 'useCurrentUser').mockReturnValue({
      id: 'u-1',
      email: 'user@example.com',
      display_name: 'User',
      role: 'user',
      must_change_password: false,
    });
    renderAt('/settings/general');
    await waitFor(() => screen.getByText('general body'));
    expect(screen.queryByRole('link', { name: /admin/i })).toBeNull();
  });

  it('renders Connectors at its top-level route for an admin user', async () => {
    vi.spyOn(currentUserModule, 'useCurrentUser').mockReturnValue({
      id: 'u-admin',
      email: 'admin@example.com',
      display_name: 'Admin',
      role: 'admin',
      must_change_password: false,
    });
    renderAt('/settings/connectors');
    await waitFor(() => screen.getByText('connectors body'));
    expect(screen.getByText('connectors body')).toBeInTheDocument();
  });

  it('redirects a non-admin away from the admin-only Connectors route', async () => {
    // The server connectors router is gated by require_active_admin, so the
    // frontend admin-gates the route too. A non-admin hitting it falls through
    // to the catch-all redirect to General rather than seeing the connectors
    // body (which would only fire 403-bound requests).
    vi.spyOn(currentUserModule, 'useCurrentUser').mockReturnValue({
      id: 'u-1',
      email: 'user@example.com',
      display_name: 'User',
      role: 'user',
      must_change_password: false,
    });
    renderAt('/settings/connectors');
    await waitFor(() => screen.getByText('general body'));
    expect(screen.queryByText('connectors body')).toBeNull();
  });

  it('shows Loading... when no current user yet', () => {
    vi.spyOn(currentUserModule, 'useCurrentUser').mockReturnValue(null);
    renderAt('/settings/general');
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
});
