import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ModelsAdminPanel } from '../ModelsAdminPanel';
import { DataProvidersAdminPanel } from '../DataProvidersAdminPanel';

vi.mock('../../../../setup/steps/TierSlotCard', () => ({
  TierSlotCard: () => null,
}));

vi.mock('../../../../setup/steps/ProviderRow', () => ({
  ProviderRow: () => null,
}));

vi.mock('../../../../setup/steps/AddProviderForm', () => ({
  AddProviderForm: () => null,
}));

describe('admin reuse wrappers', () => {
  it('ModelsAdminPanel mounts TierSlotCard heading', () => {
    render(<ModelsAdminPanel />);
    expect(screen.getByRole('heading', { name: /server-wide models/i })).toBeInTheDocument();
  });

  it('DataProvidersAdminPanel mounts heading', () => {
    render(<DataProvidersAdminPanel />);
    expect(screen.getByRole('heading', { name: /data providers/i })).toBeInTheDocument();
  });
});
