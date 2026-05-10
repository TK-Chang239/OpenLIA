import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { TimezoneSection } from '../TimezoneSection';
import * as settingsApi from '../../../../api/settings';
import type { Prefs } from '../../../../api/settings';

const BASE_PREFS: Prefs = {
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
};

describe('TimezoneSection', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders current timezone with Detected badge when auto', async () => {
    vi.spyOn(settingsApi, 'getPrefs').mockResolvedValue({
      ...BASE_PREFS,
      timezone: 'America/Los_Angeles',
      timezone_source: 'auto',
    });
    render(<TimezoneSection />);
    await waitFor(() => screen.getByText('America/Los_Angeles'));
    expect(screen.getByText(/detected/i)).toBeInTheDocument();
  });

  it('renders Manual badge when timezone_source is manual', async () => {
    vi.spyOn(settingsApi, 'getPrefs').mockResolvedValue({
      ...BASE_PREFS,
      timezone: 'Asia/Taipei',
      timezone_source: 'manual',
    });
    render(<TimezoneSection />);
    await waitFor(() => screen.getByText('Asia/Taipei'));
    expect(screen.getByText(/manual/i)).toBeInTheDocument();
  });

  it('PUTs a manual override when user picks one', async () => {
    vi.spyOn(settingsApi, 'getPrefs').mockResolvedValue({ ...BASE_PREFS });
    const updateTz = vi.spyOn(settingsApi, 'updateTimezone').mockResolvedValue({
      ...BASE_PREFS,
      timezone: 'Europe/London',
      timezone_source: 'manual',
    });
    render(<TimezoneSection />);
    await waitFor(() => screen.getByText('UTC'));
    fireEvent.click(screen.getByRole('button', { name: /override/i }));
    const select = screen.getByLabelText(/iana timezone/i);
    fireEvent.change(select, { target: { value: 'Europe/London' } });
    fireEvent.click(screen.getByRole('button', { name: /save timezone/i }));
    await waitFor(() =>
      expect(updateTz).toHaveBeenCalledWith({
        timezone: 'Europe/London',
        source: 'manual',
      }),
    );
  });

  it('PUTs the graph-extraction-time when user saves', async () => {
    vi.spyOn(settingsApi, 'getPrefs').mockResolvedValue({ ...BASE_PREFS });
    const updateTime = vi
      .spyOn(settingsApi, 'updateGraphExtractionTime')
      .mockResolvedValue({ ...BASE_PREFS, graph_extraction_time: '04:30' });
    render(<TimezoneSection />);
    await waitFor(() => screen.getByDisplayValue('03:00'));
    const input = screen.getByLabelText(/memory extraction time/i);
    fireEvent.change(input, { target: { value: '04:30' } });
    fireEvent.click(screen.getByRole('button', { name: /save extraction time/i }));
    await waitFor(() =>
      expect(updateTime).toHaveBeenCalledWith({ time: '04:30' }),
    );
  });

  it('shows an error when updateTimezone rejects', async () => {
    vi.spyOn(settingsApi, 'getPrefs').mockResolvedValue({ ...BASE_PREFS });
    vi.spyOn(settingsApi, 'updateTimezone').mockRejectedValue(
      new Error('invalid IANA timezone'),
    );
    render(<TimezoneSection />);
    await waitFor(() => screen.getByText('UTC'));
    fireEvent.click(screen.getByRole('button', { name: /override/i }));
    fireEvent.click(screen.getByRole('button', { name: /save timezone/i }));
    await waitFor(() => screen.getByText(/invalid IANA timezone/i));
  });
});
