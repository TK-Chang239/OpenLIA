import { useEffect, useState } from 'react';
import { listSkills, type SkillSummary } from '../../../api/skills';
import { SkillRow } from '../skills/SkillRow';
import { InstallSkillModal } from '../skills/InstallSkillModal';

export function SkillsSection(): JSX.Element {
  const [items, setItems] = useState<SkillSummary[] | null>(null);
  const [showInstall, setShowInstall] = useState(false);
  const refresh = () => listSkills().then(setItems);
  useEffect(() => { void refresh(); }, []);
  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Skills</h2>
        <button
          className="px-3 py-1 bg-accent-primary text-white rounded"
          onClick={() => setShowInstall(true)}
        >
          Install skill
        </button>
      </div>
      {items === null ? <p>Loading…</p>
        : items.length === 0
          ? <p className="text-text-secondary">No skills installed.</p>
          : <ul className="divide-y">
              {items.map(s => (
                <SkillRow key={`${s.scope}:${s.skill_id}`} skill={s} onChange={refresh} />
              ))}
            </ul>}
      {showInstall && (
        <InstallSkillModal
          onClose={() => setShowInstall(false)}
          onInstalled={() => { setShowInstall(false); void refresh(); }}
        />
      )}
    </div>
  );
}
