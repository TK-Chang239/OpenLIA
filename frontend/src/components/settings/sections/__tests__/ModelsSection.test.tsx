import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ModelsSection } from '../ModelsSection';
import * as settingsApi from '../../../../api/settings';

const ROSTER: settingsApi.ModelsRoster = {
  thinking: [
    {
      id: 'gpt-4o',
      model_ref: 'gpt-4o',
      display_name: 'GPT-4o',
      provider_id: 'p-openai',
      provider_kind: 'openai',
      is_tier_default: true,
      is_enabled: true,
    },
  ],
  everyday: [
    {
      id: 'gpt-4o-mini',
      model_ref: 'gpt-4o-mini',
      display_name: 'GPT-4o mini',
      provider_id: 'p-openai',
      provider_kind: 'openai',
      is_tier_default: true,
      is_enabled: true,
    },
  ],
  quick: [
    {
      id: 'haiku',
      model_ref: 'haiku',
      display_name: 'Claude Haiku',
      provider_id: 'p-anthropic',
      provider_kind: 'anthropic',
      is_tier_default: true,
      is_enabled: true,
    },
  ],
};

const DEFAULTS: settingsApi.DepartmentDefaults = {
  departments: [
    { department_id: 'secretary', tier: 'everyday', reason: 'balanced' },
    { department_id: 'equity_research', tier: 'thinking', reason: 'deep' },
  ],
};

describe('ModelsSection', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(settingsApi, 'getModelsRoster').mockResolvedValue(ROSTER);
    vi.spyOn(settingsApi, 'getModelPreferences').mockResolvedValue({
      preferences: {} as Record<settingsApi.Tier, string>,
    });
    vi.spyOn(settingsApi, 'getDepartmentDefaults').mockResolvedValue(DEFAULTS);
  });

  it('lists all three tiers with model pickers', async () => {
    render(<ModelsSection />);
    await waitFor(() => expect(screen.getByText(/Everyday/)).toBeInTheDocument());
    expect(screen.getByText(/Quick/)).toBeInTheDocument();
    expect(screen.getByText(/Thinking/)).toBeInTheDocument();
  });

  it('renders the per-department tier defaults panel', async () => {
    render(<ModelsSection />);
    await waitFor(() => screen.getByText(/per-department tier defaults/i));
    const defaultsList = screen.getByLabelText(/per-department tier defaults/i);
    expect(defaultsList.textContent).toMatch(/equity research/i);
    expect(defaultsList.textContent).toMatch(/secretary/i);
  });

  it('saves per-tier preference via PUT', async () => {
    const put = vi.spyOn(settingsApi, 'putModelPreference').mockResolvedValue({ ok: true });
    render(<ModelsSection />);
    await waitFor(() => screen.getByLabelText(/quick model/i));
    const quickSelect = screen.getByLabelText(/quick model/i) as HTMLSelectElement;
    fireEvent.change(quickSelect, { target: { value: 'haiku' } });
    const saveButtons = screen.getAllByRole('button', { name: /save/i });
    // Three tiers => three Save buttons; the third (index 2) is Quick.
    fireEvent.click(saveButtons[2]);
    await waitFor(() => expect(put).toHaveBeenCalledWith('quick', 'haiku'));
  });
});
