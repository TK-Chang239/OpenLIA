export interface SkillSummary {
  skill_id: string;
  display_name: string;
  description: string;
  version: string;
  departments: string[];
  scope: 'system' | 'user';
  enabled: boolean;
  source: string;
  installed_at: string;
}

export interface SkillAuditEntry {
  id: string;
  created_at: string;
  user_id: string | null;
  session_id: string | null;
  department_id: string | null;
  event_type: string;
  skill_id: string;
  payload: Record<string, unknown>;
}

export async function listSkillAudit(sinceDays: number): Promise<SkillAuditEntry[]> {
  const res = await fetch(`/api/admin/skills/audit?since_days=${sinceDays}`, {
    credentials: 'include',
  });
  if (!res.ok) throw new Error(`listSkillAudit: ${res.status}`);
  const json = await res.json();
  return (json.items ?? []) as SkillAuditEntry[];
}

export async function listSkills(): Promise<SkillSummary[]> {
  const res = await fetch('/api/skills', { credentials: 'include' });
  if (!res.ok) throw new Error(`listSkills: ${res.status}`);
  const json = await res.json();
  return json.items as SkillSummary[];
}

export async function toggleSkill(skillId: string, enabled: boolean) {
  const res = await fetch(`/api/skills/${encodeURIComponent(skillId)}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) throw new Error(`toggleSkill: ${res.status}`);
  return res.json();
}

export async function uninstallSkill(skillId: string) {
  const res = await fetch(`/api/skills/${encodeURIComponent(skillId)}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!res.ok && res.status !== 204) throw new Error(`uninstallSkill: ${res.status}`);
}

export async function fetchSkillBody(skillId: string): Promise<string> {
  const res = await fetch(`/api/skills/${encodeURIComponent(skillId)}/body`, {
    credentials: 'include',
  });
  if (!res.ok) throw new Error(`fetchSkillBody: ${res.status}`);
  const json = await res.json();
  return json.body as string;
}

export async function installSkillFromGit(gitUrl: string, ref?: string) {
  const fd = new FormData();
  fd.append('source_type', 'git');
  fd.append('scope', 'user');
  fd.append('git_url', gitUrl);
  if (ref) fd.append('ref', ref);
  const res = await fetch('/api/skills/install', {
    method: 'POST', credentials: 'include', body: fd,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function installSkillFromZip(file: File) {
  const fd = new FormData();
  fd.append('source_type', 'zip');
  fd.append('scope', 'user');
  fd.append('file', file);
  const res = await fetch('/api/skills/install', {
    method: 'POST', credentials: 'include', body: fd,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
