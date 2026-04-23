export type SaveState = 'idle' | 'saving' | 'saved' | 'error';

interface Props {
  state: SaveState;
  isDirty: boolean;
  onClick: () => void;
}

export function SaveButton({ state, isDirty, onClick }: Props): JSX.Element {
  const label =
    state === 'saving' ? 'Saving...' :
    state === 'saved' ? 'Saved' :
    'Save';
  const disabled = state === 'saving' || !isDirty;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-busy={state === 'saving'}
      className="rounded-md bg-accent-primary px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 hover:bg-accent-hover"
    >
      {label}
    </button>
  );
}
