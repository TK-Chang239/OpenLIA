import { useEffect, useState } from 'react';
import {
  ApiError,
  DepartmentDefaultRow,
  deleteModelPreference,
  getDepartmentDefaults,
  getModelPreferences,
  getModelsRoster,
  ModelsRoster,
  putModelPreference,
  RosterEntry,
  Tier,
} from '../../../api/settings';
import { SaveButton, SaveState } from '../SaveButton';
import { SettingGroup } from '../SettingGroup';
import { InlineFeedback } from '../InlineFeedback';

const TIERS: { tier: Tier; title: string; desc: string }[] = [
  { tier: 'thinking', title: 'Thinking', desc: 'Deep reasoning for Equity Research and Panic Thermometer.' },
  { tier: 'everyday', title: 'Everyday', desc: 'Default for Secretary and short chats.' },
  { tier: 'quick', title: 'Quick', desc: 'Fast reasoning for Retail Sentiment and wizard AI review.' },
];

interface TierRowState {
  value: string;
  state: SaveState;
  error: string | null;
  initial: string;
}

function entriesFor(roster: ModelsRoster, tier: Tier): RosterEntry[] {
  return roster[tier] ?? [];
}

export function ModelsSection(): JSX.Element {
  const [roster, setRoster] = useState<ModelsRoster | null>(null);
  const [departmentDefaults, setDepartmentDefaults] = useState<DepartmentDefaultRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState<Record<Tier, TierRowState>>({} as Record<Tier, TierRowState>);
  const [topError, setTopError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getModelsRoster(), getModelPreferences(), getDepartmentDefaults()])
      .then(([rosterResp, prefsResp, defaultsResp]) => {
        setRoster(rosterResp);
        setDepartmentDefaults(defaultsResp.departments ?? []);
        const byTier = prefsResp.preferences ?? {};
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
      {departmentDefaults.length > 0 ? (
        <SettingGroup
          title="Per-department tier defaults"
          description="Each department picks the tier that matches its workload. Hover for the rationale."
        >
          <ul role="list" aria-label="Per-department tier defaults" className="text-sm text-text-primary">
            {departmentDefaults.map((row) => (
              <li
                key={row.department_id}
                className="flex items-center justify-between border-b border-border-subtle py-1.5 last:border-0"
              >
                <span className="capitalize">{row.department_id.replaceAll('_', ' ')}</span>
                <span
                  title={row.reason}
                  aria-label={`${row.department_id} default tier ${row.tier}: ${row.reason}`}
                  className="text-text-secondary"
                >
                  {row.tier}
                </span>
              </li>
            ))}
          </ul>
        </SettingGroup>
      ) : null}
      {TIERS.map((t) => {
        const row = rows[t.tier];
        const entries = roster ? entriesFor(roster, t.tier) : [];
        const isDirty = row?.value !== row?.initial;
        return (
          <SettingGroup key={t.tier} title={t.title} description={t.desc}>
            <ul className="space-y-1 text-xs text-text-secondary">
              {entries.length === 0 ? (
                <li>(No models registered for this tier.)</li>
              ) : (
                entries.map((entry) => (
                  <li key={entry.id} className="flex justify-between gap-2">
                    <span>
                      {entry.display_name}{' '}
                      <span className="opacity-70">({entry.provider_kind})</span>
                      {entry.is_tier_default ? ' - default' : ''}
                    </span>
                    <span className={entry.is_enabled ? 'text-success' : 'text-text-tertiary'}>
                      {entry.is_enabled ? 'enabled' : 'disabled'}
                    </span>
                  </li>
                ))
              )}
            </ul>
            <div className="mt-2 flex items-center gap-3">
              <select
                aria-label={`${t.title} model`}
                value={row?.value ?? ''}
                onChange={(e) =>
                  setRows((r) => ({ ...r, [t.tier]: { ...r[t.tier], value: e.target.value } }))
                }
                className="flex-1 rounded-md border border-border-subtle bg-bg-elevated px-3 py-1.5 text-sm text-text-primary"
              >
                <option value="">(Use server default)</option>
                {entries
                  .filter((e) => e.is_enabled)
                  .map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.display_name} ({entry.provider_kind})
                    </option>
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
