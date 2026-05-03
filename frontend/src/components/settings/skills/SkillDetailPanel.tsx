import { useEffect, useState } from 'react';
import { fetchSkillBody } from '../../../api/skills';

export function SkillDetailPanel({ skillId }: { skillId: string }): JSX.Element {
  const [body, setBody] = useState<string | null>(null);
  useEffect(() => { void fetchSkillBody(skillId).then(setBody); }, [skillId]);
  return (
    <div className="mt-3 p-3 bg-surface-subtle rounded">
      {body === null ? <p>Loading body…</p>
        : <pre className="whitespace-pre-wrap text-sm">{body}</pre>}
    </div>
  );
}
