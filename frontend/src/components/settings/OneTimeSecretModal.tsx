import React, { useState } from 'react';

interface Props {
  open: boolean;
  title: string;
  secret: string;
  description?: string;
  onClose: () => void;
}

export function OneTimeSecretModal({ open, title, secret, description, onClose }: Props): JSX.Element | null {
  const [copied, setCopied] = useState(false);
  if (!open) return null;
  const copy = async () => {
    await navigator.clipboard.writeText(secret);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="ots-title" className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-surface p-6 shadow-xl">
        <h2 id="ots-title" className="text-lg font-semibold text-fg">{title}</h2>
        {description ? <p className="mt-1 text-sm text-fg-muted">{description}</p> : null}
        <div className="mt-4 rounded-md border border-border bg-surface-muted p-3 font-mono text-sm break-all text-fg">
          {secret}
        </div>
        <p className="mt-2 text-xs text-danger">You will not be able to see this again after closing.</p>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={copy} className="rounded-md border border-border px-3 py-1.5 text-sm text-fg hover:bg-surface-hover">
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button type="button" onClick={onClose} className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-hover">
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
