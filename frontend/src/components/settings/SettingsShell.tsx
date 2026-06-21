import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink, Outlet, useBlocker } from 'react-router-dom';
import { SettingsDirtyProvider, useSettingsDirty } from './dirty-context';
import { UnsavedChangesModal } from './UnsavedChangesModal';

interface NavItem {
  to: string;
  labelKey: string;
  adminOnly?: boolean;
}

const ITEMS: NavItem[] = [
  { to: '/settings/general', labelKey: 'settings.tabs.general' },
  { to: '/settings/models', labelKey: 'settings.tabs.models' },
  // Connectors are managed entirely through admin-only endpoints
  // (GET /api/connectors etc.), so the tab is admin-only — otherwise a
  // non-admin opening it fires those requests and gets a 403 error banner.
  { to: '/settings/connectors', labelKey: 'settings.tabs.connectors', adminOnly: true },
  { to: '/settings/timezone', labelKey: 'settings.tabs.timezone' },
  { to: '/settings/account', labelKey: 'settings.tabs.account' },
  { to: '/settings/disclaimer', labelKey: 'settings.tabs.disclaimer' },
  { to: '/settings/guardrails', labelKey: 'settings.tabs.guardrails' },
  { to: '/settings/skills', labelKey: 'settings.tabs.skills' },
  { to: '/settings/report-templates', labelKey: 'settings.tabs.report_templates' },
  { to: '/settings/cache', labelKey: 'settings.tabs.cache' },
  { to: '/settings/admin', labelKey: 'settings.tabs.admin', adminOnly: true },
];

interface Props {
  userRole: 'user' | 'admin';
}

function ShellInner({ userRole }: Props): JSX.Element {
  const { t } = useTranslation();
  const items = ITEMS.filter((i) => !i.adminOnly || userRole === 'admin');
  const dirtyCtx = useSettingsDirty();

  // In-app navigation guard. `useBlocker` re-evaluates on every navigation
  // attempt; we read `isAnyDirty()` lazily so the latest snapshot wins.
  const blocker = useBlocker(({ currentLocation, nextLocation }) => {
    if (!dirtyCtx) return false;
    if (currentLocation.pathname === nextLocation.pathname) return false;
    return dirtyCtx.isAnyDirty();
  });

  // Hard navigation guard (browser-level reload/close).
  useEffect(() => {
    if (!dirtyCtx) return;
    const handler = (e: BeforeUnloadEvent) => {
      if (!dirtyCtx.isAnyDirty()) return;
      e.preventDefault();
      e.returnValue = '';
      return '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirtyCtx]);

  const blockerOpen = blocker.state === 'blocked';
  return (
    <div className="flex min-h-[calc(100vh-4rem)] w-full">
      <aside className="w-56 shrink-0 border-r border-border-subtle bg-bg-base">
        <nav className="sticky top-16 p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-secondary">
            {t('settings.shell.heading')}
          </h2>
          <ul className="space-y-1">
            {items.map((i) => (
              <li key={i.to}>
                <NavLink
                  to={i.to}
                  className={({ isActive }) =>
                    `block rounded-md px-3 py-1.5 text-sm ${
                      isActive
                        ? 'bg-accent-primary/10 text-accent-primary'
                        : 'text-text-primary hover:bg-surface-hover'
                    }`
                  }
                >
                  {t(i.labelKey)}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
      <UnsavedChangesModal
        open={blockerOpen}
        onConfirmDiscard={() => blocker.proceed?.()}
        onCancel={() => blocker.reset?.()}
      />
    </div>
  );
}

export function SettingsShell(props: Props): JSX.Element {
  return (
    <SettingsDirtyProvider>
      <ShellInner {...props} />
    </SettingsDirtyProvider>
  );
}
