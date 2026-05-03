import { useState } from 'react';
import { installSkillFromGit, installSkillFromZip } from '../../../api/skills';

type Tab = 'git' | 'zip';

export function InstallSkillModal({
  onClose, onInstalled,
}: { onClose: () => void; onInstalled: () => void }): JSX.Element {
  const [tab, setTab] = useState<Tab>('git');
  const [gitUrl, setGitUrl] = useState('');
  const [ref, setRef] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const submit = async () => {
    setErr(null);
    try {
      if (tab === 'git') await installSkillFromGit(gitUrl, ref || undefined);
      else if (file) await installSkillFromZip(file);
      else throw new Error('select a file');
      onInstalled();
    } catch (e) { setErr(String(e)); }
  };
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center">
      <div className="bg-bg-base p-6 rounded shadow w-[480px]">
        <h3 className="text-lg font-semibold mb-3">Install skill</h3>
        <div className="flex gap-2 mb-3">
          {(['git', 'zip'] as Tab[]).map(t => (
            <button key={t}
              className={`px-3 py-1 rounded ${tab === t ? 'bg-accent-primary text-white' : 'bg-surface-subtle'}`}
              onClick={() => setTab(t)}
            >
              {t === 'git' ? 'Git URL' : 'Upload zip'}
            </button>
          ))}
        </div>
        {tab === 'git' && (
          <div className="space-y-2">
            <label className="block text-sm">Git URL
              <input value={gitUrl} onChange={e => setGitUrl(e.target.value)}
                className="w-full border rounded p-1" />
            </label>
            <label className="block text-sm">Branch / tag (optional)
              <input value={ref} onChange={e => setRef(e.target.value)}
                className="w-full border rounded p-1" />
            </label>
          </div>
        )}
        {tab === 'zip' && (
          <div>
            <input type="file" accept=".zip"
              onChange={e => setFile(e.target.files?.[0] ?? null)} />
          </div>
        )}
        {err && <p className="text-red-600 text-sm mt-2">{err}</p>}
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-3 py-1">Cancel</button>
          <button onClick={submit} className="px-3 py-1 bg-accent-primary text-white rounded">
            Install
          </button>
        </div>
      </div>
    </div>
  );
}
