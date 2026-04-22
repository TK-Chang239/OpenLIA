import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ModelsSection } from '../ModelsSection';
import * as settingsApi from '../../../../api/settings';

function mockCatalog() {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url: string) => {
      if (url.startsWith('/api/llm/catalog')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [
              {
                provider_id: 'openai',
                provider_label: 'OpenAI',
                models: [
                  { id: 'gpt-4o-mini', tier: 'quick', label: 'GPT-4o mini' },
                  { id: 'gpt-4o', tier: 'thinking', label: 'GPT-4o' },
                ],
              },
            ],
          }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }),
  );
}

describe('ModelsSection', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockCatalog();
  });

  it('lists all four tiers with model pickers', async () => {
    vi.spyOn(settingsApi, 'getModelPreferences').mockResolvedValue({ items: [] });
    render(<ModelsSection />);
    await waitFor(() => expect(screen.getByText(/everyday/i)).toBeInTheDocument());
    expect(screen.getByText(/quick/i)).toBeInTheDocument();
    expect(screen.getByText(/thinking/i)).toBeInTheDocument();
    expect(screen.getByText(/long context/i)).toBeInTheDocument();
  });

  it('saves per-tier preference via PUT', async () => {
    vi.spyOn(settingsApi, 'getModelPreferences').mockResolvedValue({ items: [] });
    const put = vi.spyOn(settingsApi, 'putModelPreference').mockResolvedValue({ ok: true });
    render(<ModelsSection />);
    await waitFor(() => screen.getByText(/quick/i));
    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[1], { target: { value: 'openai::gpt-4o-mini' } });
    fireEvent.click(screen.getAllByRole('button', { name: /save/i })[1]);
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('quick', { provider_id: 'openai', model_id: 'gpt-4o-mini' }),
    );
  });
});
