import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { UserOverridesPanel } from '../UserOverridesPanel';

vi.mock('../../../../api/department-model-pref', () => ({
  getDepartmentModelPref: vi.fn().mockResolvedValue({
    department_id: 'secretary',
    model_id: null,
    effective_model_id: 'M-default',
  }),
  setDepartmentModelPref: vi.fn().mockResolvedValue({}),
  clearDepartmentModelPref: vi.fn().mockResolvedValue({}),
}));

vi.mock('../../../../api/settings', () => ({
  getEnabledModels: vi.fn().mockResolvedValue([
    {
      id: 'M1',
      model_ref: 'gpt-x',
      display_name: 'GPT',
      provider_id: 'P1',
      provider_kind: 'openai',
      is_enabled: true,
    },
  ]),
}));

const DEPTS = ['secretary', 'equity_research'];

describe('UserOverridesPanel', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists every department row', async () => {
    render(<UserOverridesPanel departments={DEPTS} />);
    expect(await screen.findByText(/Secretary/i)).toBeInTheDocument();
    expect(await screen.findByText(/Equity Research/i)).toBeInTheDocument();
  });

  it('changing the dropdown calls setDepartmentModelPref', async () => {
    const { setDepartmentModelPref } = await import(
      '../../../../api/department-model-pref'
    );
    render(<UserOverridesPanel departments={DEPTS} />);
    const select = await screen.findByLabelText(/Secretary model/i);
    fireEvent.change(select, { target: { value: 'M1' } });
    await waitFor(() =>
      expect(setDepartmentModelPref).toHaveBeenCalledWith('secretary', 'M1'),
    );
  });

  it('clearing the dropdown calls clearDepartmentModelPref', async () => {
    const { clearDepartmentModelPref } = await import(
      '../../../../api/department-model-pref'
    );
    render(<UserOverridesPanel departments={DEPTS} />);
    const select = await screen.findByLabelText(/Secretary model/i);
    fireEvent.change(select, { target: { value: '' } });
    await waitFor(() =>
      expect(clearDepartmentModelPref).toHaveBeenCalledWith('secretary'),
    );
  });
});
