import { useEffect, useMemo, useState } from 'react';
import {
  getPrefs,
  updateGraphExtractionTime,
  updateTimezone,
  type ApiError,
  type Prefs,
} from '../../../api/settings';
import { SettingGroup } from '../SettingGroup';
import { InlineFeedback } from '../InlineFeedback';

const CURATED_ZONES: readonly string[] = [
  'UTC',
  'America/Los_Angeles',
  'America/Denver',
  'America/Chicago',
  'America/New_York',
  'America/Toronto',
  'America/Sao_Paulo',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Europe/Amsterdam',
  'Europe/Madrid',
  'Europe/Rome',
  'Europe/Athens',
  'Europe/Moscow',
  'Africa/Cairo',
  'Africa/Johannesburg',
  'Asia/Dubai',
  'Asia/Kolkata',
  'Asia/Bangkok',
  'Asia/Singapore',
  'Asia/Hong_Kong',
  'Asia/Shanghai',
  'Asia/Taipei',
  'Asia/Tokyo',
  'Asia/Seoul',
  'Australia/Sydney',
  'Pacific/Auckland',
];

function supportedZones(): readonly string[] {
  const intlObj = Intl as unknown as { supportedValuesOf?: (key: string) => string[] };
  if (typeof intlObj.supportedValuesOf === 'function') {
    try {
      const zones = intlObj.supportedValuesOf('timeZone');
      if (Array.isArray(zones) && zones.length > 0) return zones;
    } catch {
      /* fall through */
    }
  }
  return CURATED_ZONES;
}

export function TimezoneSection(): JSX.Element {
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Override form state.
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideZone, setOverrideZone] = useState<string>('UTC');
  const [tzSaveState, setTzSaveState] = useState<'idle' | 'saving' | 'saved'>('idle');

  // Extraction-time form state.
  const [extractionTime, setExtractionTime] = useState('03:00');
  const [extractionSaveState, setExtractionSaveState] = useState<
    'idle' | 'saving' | 'saved'
  >('idle');
  const [extractionError, setExtractionError] = useState<string | null>(null);

  const zones = useMemo(() => supportedZones(), []);

  useEffect(() => {
    let mounted = true;
    getPrefs()
      .then((p) => {
        if (!mounted) return;
        setPrefs(p);
        setOverrideZone(p.timezone);
        setExtractionTime(p.graph_extraction_time);
        setLoading(false);
      })
      .catch((e: ApiError) => {
        if (!mounted) return;
        setError(e.message);
        setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const saveTimezone = async () => {
    setTzSaveState('saving');
    setError(null);
    try {
      const next = await updateTimezone({ timezone: overrideZone, source: 'manual' });
      setPrefs(next);
      setOverrideOpen(false);
      setTzSaveState('saved');
      setTimeout(() => setTzSaveState('idle'), 1500);
    } catch (e) {
      const err = e as ApiError;
      setError(err.message ?? 'Failed to update timezone.');
      setTzSaveState('idle');
    }
  };

  const saveExtractionTime = async () => {
    setExtractionSaveState('saving');
    setExtractionError(null);
    try {
      const next = await updateGraphExtractionTime({ time: extractionTime });
      setPrefs(next);
      setExtractionSaveState('saved');
      setTimeout(() => setExtractionSaveState('idle'), 1500);
    } catch (e) {
      const err = e as ApiError;
      setExtractionError(err.message ?? 'Failed to update extraction time.');
      setExtractionSaveState('idle');
    }
  };

  if (loading) return <p className="text-sm text-text-secondary">Loading...</p>;
  if (!prefs) {
    return (
      <InlineFeedback
        kind="error"
        message={error ?? 'Failed to load preferences.'}
      />
    );
  }

  const sourceBadge =
    prefs.timezone_source === 'manual' ? (
      <span className="ml-2 rounded-md border border-accent-primary/40 bg-accent-primary/10 px-2 py-0.5 text-xs text-accent-primary">
        Manual
      </span>
    ) : (
      <span className="ml-2 rounded-md border border-border-subtle bg-bg-elevated px-2 py-0.5 text-xs text-text-secondary">
        Detected
      </span>
    );

  return (
    <div className="max-w-2xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-text-primary">Timezone & Memory</h1>
      </header>

      <InlineFeedback kind={error ? 'error' : null} message={error ?? ''} />

      <SettingGroup
        title="Timezone"
        description="Used to schedule per-user jobs (briefings, memory extraction) at the right wall-clock time."
      >
        <div className="flex items-center">
          <span className="text-sm font-medium text-text-primary">{prefs.timezone}</span>
          {sourceBadge}
          {!overrideOpen ? (
            <button
              type="button"
              onClick={() => setOverrideOpen(true)}
              className="ml-auto rounded-md border border-border-subtle bg-bg-elevated px-3 py-1 text-sm text-text-primary hover:bg-surface-hover"
            >
              Override
            </button>
          ) : null}
        </div>

        {overrideOpen ? (
          <div className="space-y-2 rounded-md border border-border-subtle bg-bg-elevated p-3">
            <label className="block">
              <span className="block text-sm font-medium text-text-primary">
                IANA timezone
              </span>
              <select
                aria-label="IANA timezone"
                value={overrideZone}
                onChange={(e) => setOverrideZone(e.target.value)}
                className="mt-1 w-full rounded-md border border-border-subtle bg-bg-base px-3 py-1.5 text-sm text-text-primary focus:border-border-secondary focus:outline-none"
              >
                {zones.map((z) => (
                  <option key={z} value={z}>
                    {z}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={saveTimezone}
                disabled={tzSaveState === 'saving'}
                className="rounded-md bg-accent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                {tzSaveState === 'saving' ? 'Saving...' : 'Save timezone'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setOverrideOpen(false);
                  setOverrideZone(prefs.timezone);
                }}
                className="rounded-md border border-border-subtle bg-bg-base px-3 py-1.5 text-sm text-text-primary hover:bg-surface-hover"
              >
                Cancel
              </button>
            </div>
            {tzSaveState === 'saved' ? (
              <p className="text-xs text-text-secondary">Saved.</p>
            ) : null}
          </div>
        ) : null}
      </SettingGroup>

      <SettingGroup
        title="Memory extraction time"
        description="Wall-clock time (in your timezone) when the nightly memory-extraction job runs."
      >
        <label className="block">
          <span className="block text-sm font-medium text-text-primary">
            Memory extraction time
          </span>
          <input
            type="time"
            aria-label="Memory extraction time"
            value={extractionTime}
            onChange={(e) => setExtractionTime(e.target.value)}
            className="mt-1 w-32 rounded-md border border-border-subtle bg-bg-elevated px-3 py-1.5 text-sm text-text-primary focus:border-border-secondary focus:outline-none"
          />
        </label>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={saveExtractionTime}
            disabled={extractionSaveState === 'saving'}
            className="rounded-md bg-accent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {extractionSaveState === 'saving'
              ? 'Saving...'
              : 'Save extraction time'}
          </button>
          {extractionSaveState === 'saved' ? (
            <span className="text-xs text-text-secondary">Saved.</span>
          ) : null}
        </div>
        <InlineFeedback
          kind={extractionError ? 'error' : null}
          message={extractionError ?? ''}
        />
      </SettingGroup>
    </div>
  );
}
