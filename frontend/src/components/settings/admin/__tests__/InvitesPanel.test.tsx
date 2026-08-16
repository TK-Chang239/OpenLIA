import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { InvitesPanel } from '../InvitesPanel';
import * as adminApi from '../../../../api/admin';

describe('InvitesPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(adminApi, 'listInvites').mockResolvedValue([
      {
        id: '00000000-0000-4000-8000-000000000001',
        label: 'beta users',
        expires_at: '2026-05-17T00:00:00Z',
        max_uses: 5,
        use_count: 1,
        revoked_at: null,
        created_at: '2026-04-17T00:00:00Z',
      },
    ]);
  });

  it('renders invite list with usage count', async () => {
    render(<InvitesPanel />);
    await waitFor(() => screen.getByText(/beta users/i));
    expect(screen.getByText('1 / 5')).toBeInTheDocument();
  });

  it('creates invite and shows one-time token modal', async () => {
    vi.spyOn(adminApi, 'createInvite').mockResolvedValue({
      id: '00000000-0000-4000-8000-000000000002',
      label: 'test',
      token: 'abc123',
    });
    render(<InvitesPanel />);
    await waitFor(() => screen.getByText(/beta users/i));
    fireEvent.click(screen.getByRole('button', { name: /new invite/i }));
    fireEvent.change(screen.getByLabelText(/label/i), { target: { value: 'test' } });
    fireEvent.click(screen.getByRole('button', { name: /create invite/i }));
    await waitFor(() =>
      expect(
        screen.getByText(/\/register\?invite=abc123/),
      ).toBeInTheDocument(),
    );
  });

  it('shows the server-provided public register URL when present', async () => {
    vi.spyOn(adminApi, 'createInvite').mockResolvedValue({
      id: '00000000-0000-4000-8000-000000000003',
      label: 'test',
      token: 'abc123',
      register_url: 'https://openlia.example.com/register?invite=abc123',
    } as adminApi.InviteCreated);
    render(<InvitesPanel />);
    await waitFor(() => screen.getByText(/beta users/i));
    fireEvent.click(screen.getByRole('button', { name: /new invite/i }));
    fireEvent.click(screen.getByRole('button', { name: /create invite/i }));
    await waitFor(() =>
      expect(
        screen.getByText('https://openlia.example.com/register?invite=abc123'),
      ).toBeInTheDocument(),
    );
  });

  it('revokes an invite after confirmation', async () => {
    const revoke = vi.spyOn(adminApi, 'revokeInvite').mockResolvedValue(undefined);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<InvitesPanel />);
    await waitFor(() => screen.getByText(/beta users/i));
    fireEvent.click(screen.getByRole('button', { name: /revoke/i }));
    await waitFor(() => expect(revoke).toHaveBeenCalledWith('00000000-0000-4000-8000-000000000001'));
  });
});
