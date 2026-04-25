import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { UsersPanel } from '../UsersPanel';
import * as adminApi from '../../../../api/admin';

describe('UsersPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(adminApi, 'listAdminUsers').mockResolvedValue([
      {
        id: '00000000-0000-4000-8000-000000000001',
        email: 'alice@x.io',
        display_name: 'Alice',
        is_admin: true,
        is_disabled: false,
        must_change_password: false,
        last_login_at: null,
      },
      {
        id: '00000000-0000-4000-8000-000000000002',
        email: 'bob@x.io',
        display_name: 'Bob',
        is_admin: false,
        is_disabled: false,
        must_change_password: false,
        last_login_at: null,
      },
    ]);
  });

  it('lists users', async () => {
    render(<UsersPanel currentUserId="00000000-0000-4000-8000-000000000001" />);
    await waitFor(() => screen.getByText('alice@x.io'));
    expect(screen.getByText('bob@x.io')).toBeInTheDocument();
  });

  it('disables a user with confirmation', async () => {
    const disable = vi.spyOn(adminApi, 'disableUser').mockResolvedValue(undefined);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<UsersPanel currentUserId="00000000-0000-4000-8000-000000000001" />);
    await waitFor(() => screen.getByText('bob@x.io'));
    const row = screen.getByText('bob@x.io').closest('tr')!;
    fireEvent.click(row.querySelector('button[data-action="disable"]')!);
    await waitFor(() =>
      expect(disable).toHaveBeenCalledWith('00000000-0000-4000-8000-000000000002'),
    );
  });

  it('blocks disabling self', async () => {
    render(<UsersPanel currentUserId="00000000-0000-4000-8000-000000000001" />);
    await waitFor(() => screen.getByText('alice@x.io'));
    const row = screen.getByText('alice@x.io').closest('tr')!;
    expect(row.querySelector('button[data-action="disable"]')).toBeNull();
  });

  it('shows server-generated temp password in OneTimeSecretModal', async () => {
    const reset = vi
      .spyOn(adminApi, 'adminResetPassword')
      .mockResolvedValue({ temporary_password: 'auto-temp-xyz' });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<UsersPanel currentUserId="00000000-0000-4000-8000-000000000001" />);
    await waitFor(() => screen.getByText('bob@x.io'));
    const row = screen.getByText('bob@x.io').closest('tr')!;
    fireEvent.click(row.querySelector('button[data-action="reset"]')!);
    await waitFor(() =>
      expect(reset).toHaveBeenCalledWith('00000000-0000-4000-8000-000000000002'),
    );
    expect(await screen.findByText('auto-temp-xyz')).toBeInTheDocument();
    expect(
      screen.getByText(/this value will not be shown again/i),
    ).toBeInTheDocument();
  });
});
