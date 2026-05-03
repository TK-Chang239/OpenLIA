import { useEffect } from 'react';
import { NavLink, Outlet, useBlocker } from 'react-router-dom';
import { SettingsDirtyProvider, useSettingsDirty } from './dirty-context';
import { UnsavedChangesModal } from './UnsavedChangesModal';

interface NavItem {
  to: string;
  label: string;
  adminOnly?: boolean;
}

const ITEMS: NavItem[] = [
  { to: '/settings/general', label: 'General' },
  { to: '/settings/models', label: 'Models' },
  { to: '/settings/account', label: 'Account' },
  { to: '/settings/disclaimer', label: 'Compliance disclaimer' },
  { to: '/settings/guardrails', label: 'Guardrail activity' },
  { to: '/settings/admin', label: 'Admin', adminOnly: true },
];

interface Props {
  userRole: 'user' | 'admin';
}

function ShellInner({ userRole }: Props): JSX.Element {
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
            Settings
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
                  {i.label}
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
