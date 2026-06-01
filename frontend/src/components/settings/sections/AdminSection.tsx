import { useTranslation } from 'react-i18next';
import { NavLink, Outlet, useMatch, useResolvedPath } from 'react-router-dom';

const TABS = [
  { to: 'invites', labelKey: 'settings.admin.tab_invites' },
  { to: 'users', labelKey: 'settings.admin.tab_users' },
  { to: 'reset-requests', labelKey: 'settings.admin.tab_reset_requests' },

  { to: 'runner-specs', labelKey: 'settings.admin.tab_runner_specs' },
  { to: 'skills', labelKey: 'settings.admin.tab_skills' },
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
  const { t } = useTranslation();
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-text-primary">{t('settings.admin.title')}</h1>
        <p className="mt-1 text-sm text-text-secondary">
          {t('settings.admin.subtitle')}
        </p>
      </header>
      <nav role="tablist" aria-label={t('settings.admin.sections_aria')} className="flex gap-1 border-b border-border-subtle">
        {TABS.map((tab) => (
          <AdminTab key={tab.to} to={tab.to} label={t(tab.labelKey)} />
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
