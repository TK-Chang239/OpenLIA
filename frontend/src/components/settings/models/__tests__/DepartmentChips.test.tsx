import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { DepartmentChips } from '../DepartmentChips';

describe('DepartmentChips', () => {
  it('shows assigned departments as filled chips', () => {
    render(
      <DepartmentChips
        departments={['secretary', 'equity_research']}
        assigned={new Set(['secretary'])}
        onToggle={() => {}}
      />,
    );
    expect(screen.getByRole('button', { name: /Secretary/i })).toHaveAttribute(
      'data-active',
      'true',
    );
    expect(
      screen.getByRole('button', { name: /Equity Research/i }),
    ).toHaveAttribute('data-active', 'false');
  });

  it('clicking a chip fires onToggle with the dept id', () => {
    const onToggle = vi.fn();
    render(
      <DepartmentChips
        departments={['secretary']}
        assigned={new Set()}
        onToggle={onToggle}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Secretary/i }));
    expect(onToggle).toHaveBeenCalledWith('secretary');
  });

  it('disabled prevents click handling', () => {
    const onToggle = vi.fn();
    render(
      <DepartmentChips
        departments={['secretary']}
        assigned={new Set()}
        onToggle={onToggle}
        disabled
      />,
    );
    const btn = screen.getByRole('button', { name: /Secretary/i });
    fireEvent.click(btn);
    expect(onToggle).not.toHaveBeenCalled();
    expect(btn).toBeDisabled();
  });
});
