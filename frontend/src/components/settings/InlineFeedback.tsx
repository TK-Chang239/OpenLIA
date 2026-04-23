interface Props {
  kind: 'success' | 'error' | null;
  message: string;
}

export function InlineFeedback({ kind, message }: Props): JSX.Element | null {
  if (!kind) return null;
  const cls =
    kind === 'error'
      ? 'text-feedback-error border-feedback-error/20 bg-feedback-error/10'
      : 'text-feedback-success border-feedback-success/20 bg-feedback-success/10';
  return (
    <div role="alert" className={`rounded-md border px-3 py-2 text-sm ${cls}`}>
      {message}
    </div>
  );
}
