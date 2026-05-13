import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ProviderCatalog } from '../ProviderCatalog';

vi.mock('../../../../api/llm_admin', () => ({
  listAdminProviders: vi.fn().mockResolvedValue([
    {
      id: 'P1',
      kind: 'openai',
      label: 'OpenAI',
      has_api_key: true,
      env_var_name: null,
      base_url: null,
      is_enabled: true,
    },
  ]),
  listAdminModelsForProvider: vi.fn().mockResolvedValue([
    {
      id: 'M1',
      provider_id: 'P1',
      model_ref: 'gpt-x',
      display_name: 'GPT X',
      is_enabled: true,
      overrides: null,
    },
  ]),
  createAdminProvider: vi.fn(),
  createAdminModel: vi.fn(),
  deleteAdminProvider: vi.fn(),
  deleteAdminModel: vi.fn(),
  updateAdminModel: vi.fn(),
  updateAdminProvider: vi.fn(),
  testAdminProviderConfig: vi.fn(),
}));

vi.mock('../../../../api/llm_slots', () => ({
  listSlotDefaults: vi.fn().mockResolvedValue({
    defaults: [
      { slot_kind: 'department', slot_id: 'secretary', model_id: 'M1' },
    ],
  }),
  setSlotDefault: vi.fn().mockResolvedValue({}),
  deleteSlotDefault: vi.fn().mockResolvedValue({}),
}));

const DEPTS = ['secretary', 'equity_research'];

describe('ProviderCatalog', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders providers and models read-only for non-admin', async () => {
    render(<ProviderCatalog departments={DEPTS} isAdmin={false} />);
    expect(await screen.findByText('OpenAI')).toBeInTheDocument();
    expect(await screen.findByText(/GPT X/)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /Add provider/i }),
    ).not.toBeInTheDocument();
  });

  it('admin sees Add provider button and chips reflect slot defaults', async () => {
    render(<ProviderCatalog departments={DEPTS} isAdmin={true} />);
    expect(
      await screen.findByRole('button', { name: /Add provider/i }),
    ).toBeInTheDocument();
    const chip = await screen.findByRole('button', {
      name: /Secretary \(default\)/i,
    });
    expect(chip).toHaveAttribute('data-active', 'true');
  });

  it('admin clicking a chip toggles the slot default', async () => {
    const { setSlotDefault, deleteSlotDefault } = await import(
      '../../../../api/llm_slots'
    );
    render(<ProviderCatalog departments={DEPTS} isAdmin={true} />);
    const erChip = await screen.findByRole('button', {
      name: /^Equity Research$/i,
    });
    fireEvent.click(erChip);
    await waitFor(() =>
      expect(setSlotDefault).toHaveBeenCalledWith(
        'department',
        'equity_research',
        'M1',
      ),
    );
    const secChip = await screen.findByRole('button', {
      name: /Secretary \(default\)/i,
    });
    fireEvent.click(secChip);
    await waitFor(() =>
      expect(deleteSlotDefault).toHaveBeenCalledWith('department', 'secretary'),
    );
  });
});
