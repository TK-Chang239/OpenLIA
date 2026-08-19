import { useEffect, useState } from 'react';
import { listSkillAudit, type SkillAuditEntry } from '../../../api/skills';

export function AdminSkillsSection(): JSX.Element {
  const [audit, setAudit] = useState<SkillAuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let mounted = true;
    listSkillAudit(30)
      .then((items) => {
        if (mounted) setAudit(items);
      })
      .catch((e: Error) => {
        if (mounted) setError(e.message);
      });
    return () => {
      mounted = false;
    };
  }, []);
  return (
    <div className="p-6 space-y-4">
      <h2 className="text-xl font-semibold">Skill Activity (admin)</h2>
      {error ? <p className="text-sm text-red-500">Failed to load skill activity: {error}</p>
        : audit === null ? <p>Loading…</p>
        : audit.length === 0 ? <p>No skill events.</p>
        : <table className="w-full text-sm">
            <thead>
              <tr><th>When</th><th>User</th><th>Event</th><th>Skill</th><th>Department</th></tr>
            </thead>
            <tbody>
              {audit.map(r => (
                <tr key={r.id}>
                  <td>{r.created_at}</td>
                  <td>{r.user_id ?? '—'}</td>
                  <td>{r.event_type}</td>
                  <td>{r.skill_id}</td>
                  <td>{r.department_id ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>}
    </div>
  );
}
