import { useEffect, useState } from 'react';

interface AuditEntry {
  id: string; created_at: string; user_id: string | null;
  session_id: string | null; department_id: string | null;
  event_type: string; skill_id: string; payload: Record<string, unknown>;
}

export function AdminSkillsSection(): JSX.Element {
  const [audit, setAudit] = useState<AuditEntry[] | null>(null);
  useEffect(() => {
    fetch('/api/admin/skills/audit?since_days=30', { credentials: 'include' })
      .then(r => r.json())
      .then(j => setAudit(j.items));
  }, []);
  return (
    <div className="p-6 space-y-4">
      <h2 className="text-xl font-semibold">Skill Activity (admin)</h2>
      {audit === null ? <p>Loading…</p>
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
