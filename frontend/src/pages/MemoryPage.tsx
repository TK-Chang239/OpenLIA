import { useMemo, useState } from 'react';
import type { JSX } from 'react';
import { useTranslation } from 'react-i18next';
import { ProposalsList } from '../components/memory/ProposalsList';
import { ConstructsList } from '../components/memory/ConstructsList';

type Tab = 'pending' | 'confirmed';

interface TabDef {
  id: Tab;
  labelKey: string;
}

const TABS: readonly TabDef[] = [
  { id: 'pending', labelKey: 'memory_page.pending_proposals' },
  { id: 'confirmed', labelKey: 'memory_page.confirmed_beliefs' },
];

export function MemoryPage(): JSX.Element {
  const { t } = useTranslation();
  const [active, setActive] = useState<Tab>('pending');
  const tabs = useMemo(() => TABS.map((tab) => ({ id: tab.id, label: t(tab.labelKey) })), [t]);

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-[52px] flex-shrink-0 items-center gap-3 border-b border-border-subtle px-6">
        <h1 className="text-[20px] font-semibold tracking-tight text-text-primary">{t('memory_page.title')}</h1>
        <span className="ml-3 border-l border-border-subtle pl-3 font-mono text-[10px] uppercase tracking-wide text-text-tertiary">
          {t('memory_page.subtitle')}
        </span>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <div
            role="tablist"
            aria-label={t('memory_page.sections_aria')}
            className="flex gap-2 border-b border-border-subtle"
          >
            {tabs.map((t) => {
              const isActive = active === t.id;
              return (
                <button
                  key={t.id}
                  role="tab"
                  type="button"
                  aria-selected={isActive}
                  aria-controls={`memory-panel-${t.id}`}
                  id={`memory-tab-${t.id}`}
                  onClick={() => setActive(t.id)}
                  className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'border-accent-primary text-accent-primary'
                      : 'border-transparent text-text-secondary hover:text-text-primary'
                  }`}
                >
                  {t.label}
                </button>
              );
            })}
          </div>

          <div
            role="tabpanel"
            id={`memory-panel-${active}`}
            aria-labelledby={`memory-tab-${active}`}
          >
            {active === 'pending' ? <ProposalsList /> : <ConstructsList />}
          </div>
        </div>
      </div>
    </div>
  );
}

export default MemoryPage;
