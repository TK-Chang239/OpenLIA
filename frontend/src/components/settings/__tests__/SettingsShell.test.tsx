import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { SettingsShell } from '../SettingsShell';

function renderAt(path: string, role: 'user' | 'admin' = 'user') {
  const router = createMemoryRouter(
    [
      {
        path: '/settings/*',
        element: <SettingsShell userRole={role} />,
        children: [
          { path: 'general', element: <p>general body</p> },
          { path: 'account', element: <p>account body</p> },
          { path: 'models', element: <p>models body</p> },
          { path: 'admin', element: <p>admin body</p> },
        ],
      },
    ],
    { initialEntries: [path] },
  );
  return render(<RouterProvider router={router} />);
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
