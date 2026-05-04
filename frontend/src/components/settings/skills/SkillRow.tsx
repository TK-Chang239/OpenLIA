import { useState } from 'react';
import { toggleSkill, uninstallSkill, type SkillSummary } from '../../../api/skills';
import { SkillDetailPanel } from './SkillDetailPanel';

export function SkillRow({
  skill, onChange,
}: { skill: SkillSummary; onChange: () => void }): JSX.Element {
  const [open, setOpen] = useState(false);
  const onToggle = async () => {
    await toggleSkill(skill.skill_id, !skill.enabled);
    onChange();
  };
  const onUninstall = async () => {
    if (!confirm(`Uninstall "${skill.display_name}"?`)) return;
    await uninstallSkill(skill.skill_id);
    onChange();
  };
  return (
    <li className="py-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-medium">{skill.display_name}</div>
          <div className="text-sm text-text-secondary">{skill.description}</div>
          <div className="text-xs text-text-tertiary mt-1">
            v{skill.version} · {skill.scope} · {skill.departments.join(', ')}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={skill.enabled} onChange={onToggle} />
            Enabled
          </label>
          <button onClick={() => setOpen(o => !o)} className="text-sm underline">
            {open ? 'Hide' : 'Details'}
          </button>
          {skill.scope === 'user' && (
            <button onClick={onUninstall} className="text-sm text-red-600 underline">
              Uninstall
            </button>
          )}
        </div>
      </div>
      {open && <SkillDetailPanel skillId={skill.skill_id} />}
    </li>
  );
}
