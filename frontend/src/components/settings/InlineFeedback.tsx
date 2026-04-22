import React from 'react';

interface Props {
  kind: 'success' | 'error' | null;
  message: string;
}

export function InlineFeedback({ kind, message }: Props): JSX.Element | null {
  if (!kind) return null;
  const cls =
    kind === 'error'
      ? 'text-danger border-danger/20 bg-danger/10'
      : 'text-success border-success/20 bg-success/10';
  return (
    <div role="alert" className={`rounded-md border px-3 py-2 text-sm ${cls}`}>
      {message}
    </div>
  );
}
