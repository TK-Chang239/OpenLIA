import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { GeneralSection } from '../GeneralSection';
import * as settingsApi from '../../../../api/settings';

describe('GeneralSection', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('loads prefs and disables save until dirty', async () => {
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
    render(<GeneralSection />);
    await waitFor(() => expect(screen.getByDisplayValue('Alice')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByRole('button', { name: /save/i })).toBeDisabled());
  });

  it('PATCHes prefs when save clicked', async () => {
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
    const update = vi.spyOn(settingsApi, 'updatePrefs').mockResolvedValue({
      display_name: 'Alice',
      theme: 'dark',
      notify_inapp: true,
      notify_email: false,
      display_language: 'en',
      response_language: 'en',
      report_language: 'en',
      timezone: 'UTC',
      timezone_source: 'auto',
      graph_extraction_time: '03:00',
    });
    render(<GeneralSection />);
    await waitFor(() => screen.getByDisplayValue('Alice'));
    fireEvent.click(screen.getByRole('radio', { name: /dark/i }));
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => expect(update).toHaveBeenCalledWith(expect.objectContaining({ theme: 'dark' })));
  });
});
