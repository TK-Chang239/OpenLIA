import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ModelsAdminPanel } from '../ModelsAdminPanel';
import * as api from '../../../../api/llm_admin';

const PROVIDER: api.AdminProvider = {
  id: 'p-1',
  kind: 'openai',
  label: 'OpenAI',
  has_api_key: true,
  env_var_name: null,
  base_url: null,
  is_enabled: true,
};

const MODEL: api.AdminModel = {
  id: 'm-1',
  provider_id: 'p-1',
  tier: 'thinking',
  model_ref: 'gpt-4o',
  display_name: 'GPT-4o',
  is_tier_default: true,
  is_enabled: true,
  overrides: null,
};

describe('ModelsAdminPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders providers and their models', async () => {
    vi.spyOn(api, 'listAdminProviders').mockResolvedValue([PROVIDER]);
    vi.spyOn(api, 'listAdminModelsForProvider').mockResolvedValue([MODEL]);
    render(<ModelsAdminPanel />);
    await waitFor(() => screen.getByRole('heading', { name: /server-wide models/i }));
    // Display name appears in the model row.
    const tables = await screen.findAllByRole('table');
    const provModelTable = tables.find((t) => t.getAttribute('aria-label') === 'Models for OpenAI');
    expect(provModelTable).toBeDefined();
    expect(provModelTable!.textContent).toMatch(/GPT-4o/);
  });

  it('shows missing-tier warnings when a tier has no enabled models', async () => {
    vi.spyOn(api, 'listAdminProviders').mockResolvedValue([PROVIDER]);
    vi.spyOn(api, 'listAdminModelsForProvider').mockResolvedValue([MODEL]);
    render(<ModelsAdminPanel />);
    await waitFor(() => screen.getByRole('heading', { name: /server-wide models/i }));
    expect(
      screen.getByText(/the everyday tier has no models configured/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/the quick tier has no models configured/i),
    ).toBeInTheDocument();
  });

  it('opens add-provider form on Add provider click', async () => {
    vi.spyOn(api, 'listAdminProviders').mockResolvedValue([]);
    render(<ModelsAdminPanel />);
    await waitFor(() =>
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole('button', { name: /add provider/i }));
    expect(screen.getByRole('form', { name: /add provider/i })).toBeInTheDocument();
  });

  it('triggers connection test when Test connection clicked', async () => {
    vi.spyOn(api, 'listAdminProviders').mockResolvedValue([]);
    const test = vi
      .spyOn(api, 'testAdminProviderConfig')
      .mockResolvedValue({ ok: true, latency_ms: 12, error_class: null, error_msg: null });
    render(<ModelsAdminPanel />);
    await waitFor(() =>
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole('button', { name: /add provider/i }));
    const labelInput = screen.getByLabelText(/^Label$/);
    fireEvent.change(labelInput, { target: { value: 'My OpenAI' } });
    const testModel = screen.getByLabelText(/test model/i);
    fireEvent.change(testModel, { target: { value: 'gpt-4o-mini' } });
    fireEvent.click(screen.getByRole('button', { name: /test connection/i }));
    await waitFor(() => expect(test).toHaveBeenCalled());
    expect(await screen.findByText(/ok \(12 ms\)/i)).toBeInTheDocument();
  });
});
