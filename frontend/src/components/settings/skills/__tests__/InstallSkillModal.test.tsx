import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { InstallSkillModal } from '../InstallSkillModal';

describe('InstallSkillModal', () => {
  it('submits a git URL', async () => {
    const fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ skill_id: 'fromgit' }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetch);
    const onInstalled = vi.fn();
    render(<InstallSkillModal onClose={() => {}} onInstalled={onInstalled} />);
    fireEvent.change(screen.getByLabelText(/git url/i), {
      target: { value: 'https://example.com/skill.git' },
    });
    fireEvent.click(screen.getByRole('button', { name: /install/i }));
    await waitFor(() => expect(onInstalled).toHaveBeenCalled());
    expect(fetch).toHaveBeenCalledWith('/api/skills/install', expect.any(Object));
  });
});
