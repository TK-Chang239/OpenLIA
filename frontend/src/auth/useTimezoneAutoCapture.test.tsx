import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { AuthProvider } from './AuthContext';
import { useTimezoneAutoCapture } from './useTimezoneAutoCapture';
import * as settingsApi from '../api/settings';
import * as authApi from '../api/auth';

function Probe(): null {
  useTimezoneAutoCapture();
  return null;
}

describe('useTimezoneAutoCapture', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('PUTs the browser timezone with source=auto once authenticated', async () => {
    vi.spyOn(authApi, 'getSession').mockResolvedValue({
      user: { id: 'u1', email: 'a@b.io', role: 'user' },
      must_change_password: false,
    } as unknown as Awaited<ReturnType<typeof authApi.getSession>>);
    const update = vi
      .spyOn(settingsApi, 'updateTimezone')
      .mockResolvedValue({} as never);

    vi.spyOn(Intl, 'DateTimeFormat').mockReturnValue({
      resolvedOptions: () => ({ timeZone: 'America/Los_Angeles' }),
    } as unknown as Intl.DateTimeFormat);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(update).toHaveBeenCalledWith({
        timezone: 'America/Los_Angeles',
        source: 'auto',
      }),
    );
  });

  it('also fires in personal-mode (getSession failure -> local user)', async () => {
    vi.spyOn(authApi, 'getSession').mockRejectedValue(new Error('no session'));
    const update = vi
      .spyOn(settingsApi, 'updateTimezone')
      .mockResolvedValue({} as never);

    vi.spyOn(Intl, 'DateTimeFormat').mockReturnValue({
      resolvedOptions: () => ({ timeZone: 'Asia/Taipei' }),
    } as unknown as Intl.DateTimeFormat);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(update).toHaveBeenCalledWith({
        timezone: 'Asia/Taipei',
        source: 'auto',
      }),
    );
  });

  it('swallows updateTimezone failures', async () => {
    vi.spyOn(authApi, 'getSession').mockRejectedValue(new Error('no session'));
    vi.spyOn(settingsApi, 'updateTimezone').mockRejectedValue(
      new Error('boom'),
    );
    vi.spyOn(Intl, 'DateTimeFormat').mockReturnValue({
      resolvedOptions: () => ({ timeZone: 'UTC' }),
    } as unknown as Intl.DateTimeFormat);
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(warn).toHaveBeenCalled());
  });
});
