import { NavLink, Outlet, useMatch, useResolvedPath } from 'react-router-dom';

const TABS = [
  { to: 'invites', label: 'Invites' },
  { to: 'users', label: 'Users' },
  { to: 'reset-requests', label: 'Reset requests' },
  { to: 'models', label: 'Models' },
  { to: 'data-providers', label: 'Data providers' },
];

function AdminTab({ to, label }: { to: string; label: string }): JSX.Element {
  const resolved = useResolvedPath(to);
  const match = useMatch({ path: resolved.pathname, end: false });
  const isActive = match !== null;
  return (
    <NavLink
      to={to}
      role="tab"
      aria-selected={isActive ? 'true' : 'false'}
      className={`border-b-2 px-3 py-2 text-sm ${
        isActive
          ? 'border-accent-primary text-accent-primary'
          : 'border-transparent text-text-primary hover:text-accent-primary'
      }`}
    >
      {label}
    </NavLink>
  );
}

export function AdminSection(): JSX.Element {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-text-primary">Admin</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Manage users, invites, password resets, server-wide models, and data providers.
        </p>
      </header>
      <nav role="tablist" aria-label="Admin sections" className="flex gap-1 border-b border-border-subtle">
        {TABS.map((t) => (
          <AdminTab key={t.to} to={t.to} label={t.label} />
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
