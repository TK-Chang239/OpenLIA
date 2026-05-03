import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SkillLoadedCard } from '../SkillLoadedCard';

describe('SkillLoadedCard', () => {
  it('renders skill display name', () => {
    render(<SkillLoadedCard skillId="alpha" displayName="Alpha Skill" />);
    expect(screen.getByText(/Alpha Skill/)).toBeInTheDocument();
  });
});
