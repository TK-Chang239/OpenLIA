import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider, Link } from 'react-router-dom';
import { SettingsShell } from '../SettingsShell';
import { useDirtyForm } from '../useDirtyForm';

function DirtySection() {
  const form = useDirtyForm({ name: 'initial' });
  return (
    <div>
      <p>section: {form.values.name}</p>
      <button type="button" onClick={() => form.setField('name', 'changed')}>
        make dirty
      </button>
      <Link to="/settings/account">go account</Link>
      <Link to="/settings/general">go general</Link>
    </div>
  );
}

function renderShell(initialPath: string) {
  const router = createMemoryRouter(
    [
      {
        path: '/settings/*',
        element: <SettingsShell userRole="user" />,
        children: [
          { path: 'general', element: <DirtySection /> },
          { path: 'account', element: <p>account body</p> },
        ],
      },
    ],
    { initialEntries: [initialPath] },
  );
  return { router, ...render(<RouterProvider router={router} />) };
}

describe('SettingsShell unsaved-changes guard', () => {
  it('opens unsaved-changes modal when navigating away dirty', () => {
    renderShell('/settings/general');
    fireEvent.click(screen.getByRole('button', { name: /make dirty/i }));
    fireEvent.click(screen.getByRole('link', { name: /go account/i }));
    expect(
      screen.getByRole('heading', { name: /discard unsaved changes/i }),
    ).toBeInTheDocument();
  });

  it('Stay keeps the URL on the current section', () => {
    const { router } = renderShell('/settings/general');
    fireEvent.click(screen.getByRole('button', { name: /make dirty/i }));
    fireEvent.click(screen.getByRole('link', { name: /go account/i }));
    fireEvent.click(screen.getByRole('button', { name: /^stay$/i }));
    expect(router.state.location.pathname).toBe('/settings/general');
  });

  it('Discard closes the modal (navigation is unblocked)', async () => {
    renderShell('/settings/general');
    fireEvent.click(screen.getByRole('button', { name: /make dirty/i }));
    fireEvent.click(screen.getByRole('link', { name: /go account/i }));
    expect(
      screen.getByRole('heading', { name: /discard unsaved changes/i }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /discard/i }));
    await waitFor(() =>
      expect(
        screen.queryByRole('heading', { name: /discard unsaved changes/i }),
      ).not.toBeInTheDocument(),
    );
  });
});
