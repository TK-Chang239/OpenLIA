import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SystemRolesPanel } from '../SystemRolesPanel';

vi.mock('../../../../api/llm_slots', () => ({
  listSlotDefaults: vi.fn().mockResolvedValue({
    defaults: [
      { slot_kind: 'system_role', slot_id: 'ai_review', model_id: 'M1' },
    ],
  }),
  setSlotDefault: vi.fn().mockResolvedValue({}),
}));

vi.mock('../../../../api/settings', () => ({
  getEnabledModels: vi.fn().mockResolvedValue([
    {
      id: 'M1',
      model_ref: 'gpt-x',
      display_name: 'GPT X',
      provider_id: 'P1',
      provider_kind: 'openai',
      is_enabled: true,
    },
    {
      id: 'M2',
      model_ref: 'claude',
      display_name: 'Claude',
      provider_id: 'P2',
      provider_kind: 'anthropic',
      is_enabled: true,
    },
  ]),
}));

describe('SystemRolesPanel', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists all five system roles with current assignment preselected', async () => {
    render(<SystemRolesPanel />);
    expect(await screen.findByText(/Wizard AI review/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Connector agentic resolver/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Connector spec adapter/i)).toBeInTheDocument();
    expect(screen.getByText(/Graph memory extraction/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Graph memory summarization/i),
    ).toBeInTheDocument();
    const sel = (await screen.findByLabelText(
      /Wizard AI review model/i,
    )) as HTMLSelectElement;
    await waitFor(() => expect(sel.value).toBe('M1'));
  });

  it('changing dropdown calls setSlotDefault with system_role', async () => {
    const { setSlotDefault } = await import('../../../../api/llm_slots');
    render(<SystemRolesPanel />);
    const sel = await screen.findByLabelText(/Graph memory extraction model/i);
    fireEvent.change(sel, { target: { value: 'M2' } });
    await waitFor(() =>
      expect(setSlotDefault).toHaveBeenCalledWith(
        'system_role',
        'graph_extraction',
        'M2',
      ),
    );
  });
});
