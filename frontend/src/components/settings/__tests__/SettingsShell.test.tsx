import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { SettingsShell } from '../SettingsShell';

function renderAt(path: string, role: 'user' | 'admin' = 'user') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/settings/*" element={<SettingsShell userRole={role} />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('SettingsShell', () => {
  it('renders nav items for regular user (no Admin)', () => {
    renderAt('/settings/general');
    expect(screen.getByRole('link', { name: /general/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /models/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /account/i })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /admin/i })).toBeNull();
  });

  it('renders Admin nav item when role is admin', () => {
    renderAt('/settings/general', 'admin');
    expect(screen.getByRole('link', { name: /admin/i })).toBeInTheDocument();
  });

  it('marks the active section', () => {
    renderAt('/settings/account');
    const link = screen.getByRole('link', { name: /account/i });
    expect(link).toHaveAttribute('aria-current', 'page');
  });
});
