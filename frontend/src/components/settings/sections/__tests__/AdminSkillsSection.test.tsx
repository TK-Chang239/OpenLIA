import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { AdminSkillsSection } from '../AdminSkillsSection';

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
    if (url.includes('/audit')) {
      return Promise.resolve(new Response(JSON.stringify({
        items: [{
          id: '1', created_at: '2026-05-03T00:00:00Z', user_id: 'u',
          session_id: 's', department_id: 'secretary',
          event_type: 'skill_loaded', skill_id: 'alpha', payload: {},
        }],
      }), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
  }));
});

describe('AdminSkillsSection', () => {
  it('renders system skills + audit log tabs', async () => {
    render(<AdminSkillsSection />);
    await waitFor(() => expect(screen.getByText(/skill_loaded/i)).toBeInTheDocument());
  });
});
