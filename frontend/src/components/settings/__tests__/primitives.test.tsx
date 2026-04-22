import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { SaveButton } from '../SaveButton';
import { InlineFeedback } from '../InlineFeedback';
import { ToggleSwitch } from '../ToggleSwitch';
import { OneTimeSecretModal } from '../OneTimeSecretModal';

describe('SaveButton', () => {
  it('disabled when not dirty', () => {
    render(<SaveButton state="idle" isDirty={false} onClick={() => {}} />);
    expect(screen.getByRole('button')).toBeDisabled();
  });
  it('shows "Saving..." while saving', () => {
    render(<SaveButton state="saving" isDirty={true} onClick={() => {}} />);
    expect(screen.getByRole('button')).toHaveTextContent(/saving/i);
  });
  it('shows "Saved" after success', () => {
    render(<SaveButton state="saved" isDirty={false} onClick={() => {}} />);
    expect(screen.getByRole('button')).toHaveTextContent(/saved/i);
  });
});

describe('InlineFeedback', () => {
  it('renders nothing when kind is null', () => {
    const { container } = render(<InlineFeedback kind={null} message="" />);
    expect(container.firstChild).toBeNull();
  });
  it('renders error message', () => {
    render(<InlineFeedback kind="error" message="bad" />);
    expect(screen.getByRole('alert')).toHaveTextContent('bad');
  });
});

describe('ToggleSwitch', () => {
  it('fires onChange when clicked', () => {
    const cb = vi.fn();
    render(<ToggleSwitch checked={false} onChange={cb} label="X" />);
    fireEvent.click(screen.getByRole('switch'));
    expect(cb).toHaveBeenCalledWith(true);
  });
});

describe('OneTimeSecretModal', () => {
  it('shows secret and copy button when open', () => {
    render(<OneTimeSecretModal open={true} title="Invite token" secret="abc123" onClose={() => {}} />);
    expect(screen.getByText('abc123')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument();
  });
  it('renders nothing when closed', () => {
    const { container } = render(<OneTimeSecretModal open={false} title="x" secret="x" onClose={() => {}} />);
    expect(container.firstChild).toBeNull();
  });
});
