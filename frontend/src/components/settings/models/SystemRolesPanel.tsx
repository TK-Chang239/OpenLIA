import { useEffect, useState } from 'react';
import { getEnabledModels, RosterEntry } from '../../../api/settings';
import { listSlotDefaults, setSlotDefault } from '../../../api/llm_slots';

const SYSTEM_ROLES: { id: string; label: string }[] = [
  { id: 'connector_agentic_resolver', label: 'Connector agentic resolver' },
  { id: 'connector_spec_adapter', label: 'Connector spec adapter' },
  { id: 'graph_extraction', label: 'Graph memory extraction' },
  { id: 'graph_summarization', label: 'Graph memory summarization' },
];

export function SystemRolesPanel(): JSX.Element {
  const [models, setModels] = useState<RosterEntry[]>([]);
  const [assignments, setAssignments] = useState<Record<string, string>>({});

  useEffect(() => {
    Promise.all([getEnabledModels(), listSlotDefaults()]).then(([m, s]) => {
      setModels(m);
      const out: Record<string, string> = {};
      for (const d of s.defaults) {
        if (d.slot_kind === 'system_role') out[d.slot_id] = d.model_id;
      }
      setAssignments(out);
    });
  }, []);

  const onChange = async (roleId: string, modelId: string) => {
    if (!modelId) return;
    await setSlotDefault('system_role', roleId, modelId);
    setAssignments((prev) => ({ ...prev, [roleId]: modelId }));
  };

  return (
    <section className="space-y-3">
      <header>
        <h2 className="text-lg font-semibold text-text-primary">
          System roles
        </h2>
        <p className="text-sm text-text-secondary">
          Pick a model for each internal job (wizard review, graph memory,
          etc.). No user override.
        </p>
      </header>
      <table className="w-full text-sm">
        <tbody>
          {SYSTEM_ROLES.map(({ id, label }) => (
            <tr key={id} className="border-b border-border-subtle">
              <td className="py-2 pr-2 text-text-primary">{label}</td>
              <td className="py-2">
                <select
                  aria-label={`${label} model`}
                  value={assignments[id] ?? ''}
                  onChange={(e) => onChange(id, e.target.value)}
                  className="w-full rounded-md border border-border-subtle bg-bg-elevated px-2 py-1 text-text-primary"
                >
                  <option value="">(Unassigned)</option>
                  {models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.display_name} ({m.provider_kind})
                    </option>
                  ))}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
