import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { SkillsSection } from '../../sections/SkillsSection';

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
    new Response(JSON.stringify({
      items: [{
        skill_id: 'alpha', display_name: 'Alpha', description: 'd',
        version: '1', departments: ['secretary'], scope: 'user',
        enabled: true, source: 'folder', installed_at: '2026-05-03T00:00:00Z',
      }],
    }), { status: 200 }),
  ));
});

describe('SkillsSection', () => {
  it('renders installed skills', async () => {
    render(<SkillsSection />);
    await waitFor(() => expect(screen.getByText('Alpha')).toBeInTheDocument());
  });
});
