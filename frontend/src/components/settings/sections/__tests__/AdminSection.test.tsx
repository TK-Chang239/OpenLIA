import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AdminSection } from '../AdminSection';

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/settings/admin/*" element={<AdminSection />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('AdminSection', () => {
  it('renders all admin tabs', () => {
    renderAt('/settings/admin/invites');
    expect(screen.getByRole('tab', { name: /invites/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /users/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /reset requests/i })).toBeInTheDocument();
  });

  it('no longer shows a runner specs tab', () => {
    renderAt('/settings/admin/invites');
    expect(screen.queryByRole('tab', { name: /runner specs/i })).toBeNull();
  });

  it('no longer shows a Connectors tab (now a top-level settings tab)', () => {
    renderAt('/settings/admin/invites');
    expect(screen.queryByRole('tab', { name: /connectors/i })).toBeNull();
  });

  it('marks the active tab', () => {
    renderAt('/settings/admin/users');
    expect(screen.getByRole('tab', { name: /users/i })).toHaveAttribute('aria-selected', 'true');
  });
});
