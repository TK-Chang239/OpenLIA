import { useEffect, useState } from 'react';
import { deleteModelPreference, getModelPreferences, putModelPreference, Tier, ApiError } from '../../../api/settings';
import { SaveButton, SaveState } from '../SaveButton';
import { SettingGroup } from '../SettingGroup';
import { InlineFeedback } from '../InlineFeedback';

interface CatalogModel {
  id: string;
  tier: Tier;
  label: string;
}
interface CatalogProvider {
  provider_id: string;
  provider_label: string;
  models: CatalogModel[];
}

const TIERS: { tier: Tier; title: string; desc: string }[] = [
  { tier: 'everyday', title: 'Everyday', desc: 'Default for Secretary and short chats.' },
  { tier: 'quick', title: 'Quick', desc: 'Fast reasoning for Retail Sentiment and wizard AI review.' },
  { tier: 'thinking', title: 'Thinking', desc: 'Deep reasoning for Equity Research and Panic Thermometer.' },
];

interface TierRowState {
  value: string;
  state: SaveState;
  error: string | null;
  initial: string;
}

export function ModelsSection(): JSX.Element {
  const [catalog, setCatalog] = useState<CatalogProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState<Record<Tier, TierRowState>>({} as Record<Tier, TierRowState>);
  const [topError, setTopError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch('/api/llm/catalog', { credentials: 'same-origin' }).then((r) => r.json()),
      getModelPreferences(),
    ])
      .then(([cat, prefs]) => {
        setCatalog(cat.items ?? []);
        const byTier = prefs.preferences ?? {};
        const next = {} as Record<Tier, TierRowState>;
        for (const t of TIERS) {
          const v = byTier[t.tier] ?? '';
          next[t.tier] = { value: v, state: 'idle', error: null, initial: v };
        }
        setRows(next);
        setLoading(false);
      })
      .catch((e: ApiError) => {
        setTopError(e.message);
        setLoading(false);
      });
  }, []);

  const optionsFor = (tier: Tier): { value: string; label: string }[] => {
    const opts: { value: string; label: string }[] = [];
    for (const prov of catalog) {
      for (const m of prov.models) {
        if (m.tier === tier) {
          opts.push({ value: m.id, label: `${prov.provider_label} — ${m.label}` });
        }
      }
    }
    return opts;
  };

  const save = async (tier: Tier) => {
    setRows((r) => ({ ...r, [tier]: { ...r[tier], state: 'saving', error: null } }));
    try {
      const value = rows[tier].value;
      if (value) {
        await putModelPreference(tier, value);
      } else {
        await deleteModelPreference(tier);
      }
      setRows((r) => ({ ...r, [tier]: { ...r[tier], state: 'saved', initial: r[tier].value } }));
      setTimeout(() => setRows((r) => ({ ...r, [tier]: { ...r[tier], state: 'idle' } })), 1500);
    } catch (e) {
      const err = e as ApiError;
      setRows((r) => ({ ...r, [tier]: { ...r[tier], state: 'error', error: err.message } }));
    }
  };

  if (loading) return <p className="text-sm text-text-secondary">Loading...</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-text-primary">Models</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Choose a preferred model per tier. Overrides server defaults for your account.
        </p>
      </header>
      <InlineFeedback kind={topError ? 'error' : null} message={topError ?? ''} />
      {TIERS.map((t) => {
        const row = rows[t.tier];
        const opts = optionsFor(t.tier);
        const isDirty = row?.value !== row?.initial;
        return (
          <SettingGroup key={t.tier} title={t.title} description={t.desc}>
            <div className="flex items-center gap-3">
              <select
                aria-label={`${t.title} model`}
                value={row?.value ?? ''}
                onChange={(e) =>
                  setRows((r) => ({ ...r, [t.tier]: { ...r[t.tier], value: e.target.value } }))
                }
                className="flex-1 rounded-md border border-border-subtle bg-bg-elevated px-3 py-1.5 text-sm text-text-primary"
              >
                <option value="">(Use server default)</option>
                {opts.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
              <SaveButton state={row?.state ?? 'idle'} isDirty={isDirty} onClick={() => save(t.tier)} />
            </div>
            {row?.error ? <InlineFeedback kind="error" message={row.error} /> : null}
          </SettingGroup>
        );
      })}
    </div>
  );
}
