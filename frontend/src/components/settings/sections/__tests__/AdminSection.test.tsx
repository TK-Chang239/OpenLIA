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
  it('renders all five admin tabs', () => {
    renderAt('/settings/admin/invites');
    expect(screen.getByRole('tab', { name: /invites/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /users/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /reset requests/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /models/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /data providers/i })).toBeInTheDocument();
  });

  it('marks the active tab', () => {
    renderAt('/settings/admin/users');
    expect(screen.getByRole('tab', { name: /users/i })).toHaveAttribute('aria-selected', 'true');
  });
});
