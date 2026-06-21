import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, it, expect, vi } from 'vitest';
import { ModelsSection } from '../ModelsSection';
import { listAdminProviders } from '../../../../api/llm_admin';

vi.mock('../../../../api/department-model-pref', () => ({
  getDepartmentModelPref: vi.fn().mockResolvedValue({
    department_id: '',
    model_id: null,
    effective_model_id: null,
  }),
  setDepartmentModelPref: vi.fn(),
  clearDepartmentModelPref: vi.fn(),
}));
vi.mock('../../../../api/settings', () => ({
  getEnabledModels: vi.fn().mockResolvedValue([]),
  getRegisteredDepartmentIds: vi
    .fn()
    .mockResolvedValue(['secretary', 'equity_research']),
}));
vi.mock('../../../../api/llm_admin', () => ({
  listAdminProviders: vi.fn().mockResolvedValue([]),
  listAdminModelsForProvider: vi.fn().mockResolvedValue([]),
  createAdminProvider: vi.fn(),
  createAdminModel: vi.fn(),
  deleteAdminProvider: vi.fn(),
  deleteAdminModel: vi.fn(),
  updateAdminModel: vi.fn(),
  updateAdminProvider: vi.fn(),
  testAdminProviderConfig: vi.fn(),
}));
vi.mock('../../../../api/llm_slots', () => ({
  listSlotDefaults: vi.fn().mockResolvedValue({ defaults: [] }),
  setSlotDefault: vi.fn(),
  deleteSlotDefault: vi.fn(),
}));

describe('ModelsSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders user overrides, catalog, system roles for admin', async () => {
    render(<ModelsSection userRole="admin" />);
    await waitFor(() =>
      expect(
        screen.getByText(/Your defaults per department/i),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText(/Providers and models/i)).toBeInTheDocument();
    expect(screen.getByText(/System roles/i)).toBeInTheDocument();
  });

  it('hides the admin catalog for non-admin and never calls the admin endpoint', async () => {
    render(<ModelsSection userRole="user" />);
    await waitFor(() =>
      expect(
        screen.getByText(/Your defaults per department/i),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByText(/System roles/i)).not.toBeInTheDocument();
    // The provider catalog (admin-only fetch) must not render for non-admins,
    // otherwise listAdminProviders 403s and shows an error banner.
    expect(screen.queryByText(/Providers and models/i)).not.toBeInTheDocument();
    expect(listAdminProviders).not.toHaveBeenCalled();
  });
});
