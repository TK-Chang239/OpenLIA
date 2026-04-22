import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ResetRequestsPanel } from '../ResetRequestsPanel';
import * as adminApi from '../../../../api/admin';

describe('ResetRequestsPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(adminApi, 'listResetRequests').mockResolvedValue([
      {
        id: '00000000-0000-4000-8000-000000000001',
        user_id: '00000000-0000-4000-8000-000000000005',
        requested_at: '2026-04-17T00:00:00Z',
        requested_ip: '1.2.3.4',
        status: 'pending',
      },
    ]);
  });

  it('lists pending requests by default', async () => {
    render(<ResetRequestsPanel />);
    await waitFor(() => screen.getByText('00000000-0000-4000-8000-000000000005'));
    expect(screen.getByText('1.2.3.4')).toBeInTheDocument();
  });

  it('approves and shows one-time reset token', async () => {
    vi.spyOn(adminApi, 'approveResetRequest').mockResolvedValue({
      reset_token: 'tok123',
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<ResetRequestsPanel />);
    await waitFor(() => screen.getByText('00000000-0000-4000-8000-000000000005'));
    fireEvent.click(screen.getByRole('button', { name: /approve/i }));
    await waitFor(() =>
      expect(screen.getByText(/tok123/)).toBeInTheDocument(),
    );
  });

  it('rejects a request', async () => {
    const reject = vi.spyOn(adminApi, 'rejectResetRequest').mockResolvedValue(undefined);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<ResetRequestsPanel />);
    await waitFor(() => screen.getByText('00000000-0000-4000-8000-000000000005'));
    fireEvent.click(screen.getByRole('button', { name: /reject/i }));
    await waitFor(() => expect(reject).toHaveBeenCalledWith('00000000-0000-4000-8000-000000000001'));
  });
});
