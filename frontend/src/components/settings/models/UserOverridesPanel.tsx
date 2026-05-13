import { useEffect, useState } from 'react';
import { getEnabledModels, RosterEntry } from '../../../api/settings';
import {
  clearDepartmentModelPref,
  getDepartmentModelPref,
  setDepartmentModelPref,
} from '../../../api/department-model-pref';

interface Props {
  departments: string[];
}

interface Row {
  department_id: string;
  selected: string;
  effective: string | null;
}

function humanize(id: string): string {
  return id.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function UserOverridesPanel({ departments }: Props): JSX.Element {
  const [models, setModels] = useState<RosterEntry[]>([]);
  const [rows, setRows] = useState<Row[]>([]);

  useEffect(() => {
    Promise.all([
      getEnabledModels(),
      Promise.all(
        departments.map((d) =>
          getDepartmentModelPref(d).then((p) => ({
            department_id: d,
            selected: p.model_id ?? '',
            effective: p.effective_model_id,
          })),
        ),
      ),
    ]).then(([m, r]) => {
      setModels(m);
      setRows(r);
    });
  }, [departments]);

  const onChange = async (idx: number, value: string) => {
    const row = rows[idx];
    if (value) {
      await setDepartmentModelPref(row.department_id, value);
    } else {
      await clearDepartmentModelPref(row.department_id);
    }
    setRows((prev) =>
      prev.map((r, i) => (i === idx ? { ...r, selected: value } : r)),
    );
  };

  return (
    <section className="space-y-3">
      <header>
        <h2 className="text-lg font-semibold text-text-primary">
          Your defaults per department
        </h2>
        <p className="text-sm text-text-secondary">
          Override the model used when you run each department. Falls back to the
          server default if not set.
        </p>
      </header>
      <table className="w-full text-sm">
        <tbody>
          {rows.map((row, idx) => (
            <tr
              key={row.department_id}
              className="border-b border-border-subtle"
            >
              <td className="py-2 pr-2 text-text-primary">
                {humanize(row.department_id)}
              </td>
              <td className="py-2">
                <select
                  aria-label={`${humanize(row.department_id)} model`}
                  value={row.selected}
                  onChange={(e) => onChange(idx, e.target.value)}
                  className="w-full rounded-md border border-border-subtle bg-bg-elevated px-2 py-1 text-text-primary"
                >
                  <option value="">(Use server default)</option>
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
