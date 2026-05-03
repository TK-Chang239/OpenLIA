import type { JSX } from 'react';

export function SkillLoadedCard({
  skillId, displayName,
}: { skillId: string; displayName: string }): JSX.Element {
  return (
    <div className="my-2 px-3 py-2 bg-surface-subtle rounded text-sm border-l-2 border-accent-primary">
      <span className="text-text-secondary">Loaded skill:</span>{' '}
      <code>{displayName}</code>
      <span className="text-text-tertiary ml-2">({skillId})</span>
    </div>
  );
}
