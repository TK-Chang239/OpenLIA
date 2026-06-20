import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AccountSection } from '../AccountSection';
import * as settingsApi from '../../../../api/settings';

vi.mock('../../../auth/ChangePasswordForm', () => ({
  ChangePasswordForm: () => <div data-testid="change-password-form" />,
}));

vi.mock('../../../auth/SessionsPanel', () => ({
  SessionsPanel: () => <div data-testid="sessions-panel" />,
}));

describe('AccountSection', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(settingsApi, 'getPrefs').mockResolvedValue({
      display_name: 'Alice',
      theme: 'system',
      notify_inapp: true,
      notify_email: false,
      display_language: 'en',
      response_language: 'en',
      report_language: 'en',
      timezone: 'UTC',
      timezone_source: 'auto',
      graph_extraction_time: '03:00',
    });
  });

  it('renders email change form and sub-forms', async () => {
    render(<AccountSection currentEmail="alice@x.io" mustChangePassword={false} />);
    await waitFor(() => screen.getByDisplayValue('alice@x.io'));
    expect(screen.getByTestId('change-password-form')).toBeInTheDocument();
    expect(screen.getByTestId('sessions-panel')).toBeInTheDocument();
  });

  it('submits email change with password', async () => {
    const update = vi.spyOn(settingsApi, 'updateEmail').mockResolvedValue({ ok: true } as any);
    render(<AccountSection currentEmail="alice@x.io" mustChangePassword={false} />);
    await waitFor(() => screen.getByDisplayValue('alice@x.io'));
    fireEvent.change(screen.getByLabelText(/new email/i), { target: { value: 'new@x.io' } });
    fireEvent.change(screen.getByLabelText(/current password/i), { target: { value: 'pw' } });
    fireEvent.click(screen.getByRole('button', { name: /change email/i }));
    await waitFor(() =>
      expect(update).toHaveBeenCalledWith({ new_email: 'new@x.io', current_password: 'pw' }),
    );
  });

  it('shows must-change-password banner when flag is set', () => {
    render(<AccountSection currentEmail="a@b.c" mustChangePassword={true} />);
    expect(screen.getByRole('alert')).toHaveTextContent(/must change your password/i);
  });

  it('does not render language preference controls (moved to General settings)', async () => {
    render(<AccountSection currentEmail="a@b.c" mustChangePassword={false} />);
    await waitFor(() => screen.getByDisplayValue('a@b.c'));
    expect(screen.queryByRole('button', { name: /save languages/i })).toBeNull();
  });

  it('does not render a Sign out button (sign-out lives in the sidebar)', () => {
    render(<AccountSection currentEmail="a@b.c" mustChangePassword={false} />);
    expect(screen.queryByRole('button', { name: /sign out/i })).toBeNull();
  });
});
