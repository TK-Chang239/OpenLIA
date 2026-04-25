import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { DataProvidersAdminPanel } from '../DataProvidersAdminPanel';
import * as api from '../../../../api/data_providers';
import { ApiError } from '../../../../api/_request';

const PROVIDER: api.DataProvider = {
  id: 'p-1',
  kind: 'eodhd',
  label: 'EODHD',
  category: 'financial',
  mode: 'api_key',
  base_url: null,
  mcp_url: null,
  env_var_name: null,
  has_api_key: true,
  is_enabled: true,
  extra_config: {},
};

describe('DataProvidersAdminPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders providers from /data-providers', async () => {
    vi.spyOn(api, 'listDataProviders').mockResolvedValue({ providers: [PROVIDER] });
    vi.spyOn(api, 'listRequirementMappings').mockResolvedValue({ mappings: [] });
    render(<DataProvidersAdminPanel />);
    await waitFor(() => screen.getByText('EODHD'));
    expect(screen.getByText('EODHD')).toBeInTheDocument();
    expect(screen.getByText(/financial/i)).toBeInTheDocument();
  });

  it('creates a new provider via the inline form', async () => {
    vi.spyOn(api, 'listDataProviders')
      .mockResolvedValueOnce({ providers: [] })
      .mockResolvedValue({ providers: [PROVIDER] });
    vi.spyOn(api, 'listRequirementMappings').mockResolvedValue({ mappings: [] });
    const create = vi.spyOn(api, 'createDataProvider').mockResolvedValue(PROVIDER);
    render(<DataProvidersAdminPanel />);
    await waitFor(() => screen.getByRole('heading', { name: /data providers/i }));
    fireEvent.click(screen.getByRole('button', { name: /add provider/i }));
    fireEvent.change(screen.getByLabelText(/^Kind$/), { target: { value: 'eodhd' } });
    fireEvent.change(screen.getByLabelText(/^Label$/), { target: { value: 'EODHD' } });
    fireEvent.click(screen.getByRole('button', { name: /save provider/i }));
    await waitFor(() =>
      expect(create).toHaveBeenCalledWith(
        expect.objectContaining({ kind: 'eodhd', label: 'EODHD', category: 'financial' }),
      ),
    );
  });

  it('shows a 409 conflict message when deleting a mapped provider', async () => {
    vi.spyOn(api, 'listDataProviders').mockResolvedValue({ providers: [PROVIDER] });
    vi.spyOn(api, 'listRequirementMappings').mockResolvedValue({ mappings: [] });
    vi.spyOn(api, 'deleteDataProvider').mockRejectedValue(
      new ApiError(409, 'provider_in_use', 'in use'),
    );
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<DataProvidersAdminPanel />);
    await waitFor(() => screen.getByText('EODHD'));
    fireEvent.click(screen.getByRole('button', { name: /delete/i }));
    expect(
      await screen.findByText(/in use by a requirement mapping/i),
    ).toBeInTheDocument();
  });

  it('runs a connection test', async () => {
    vi.spyOn(api, 'listDataProviders').mockResolvedValue({ providers: [PROVIDER] });
    vi.spyOn(api, 'listRequirementMappings').mockResolvedValue({ mappings: [] });
    const test = vi
      .spyOn(api, 'testDataProviderConnection')
      .mockResolvedValue({ ok: true });
    render(<DataProvidersAdminPanel />);
    await waitFor(() => screen.getByText('EODHD'));
    fireEvent.click(screen.getByRole('button', { name: /^test$/i }));
    await waitFor(() => expect(test).toHaveBeenCalledWith('p-1'));
    expect(await screen.findByText(/connection healthy/i)).toBeInTheDocument();
  });
});
