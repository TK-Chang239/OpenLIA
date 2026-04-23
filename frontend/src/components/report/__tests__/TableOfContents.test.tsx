import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TableOfContents } from '../TableOfContents';

describe('TableOfContents', () => {
  it('renders one link per section', () => {
    render(
      <TableOfContents
        sections={[
          { id: 'fin', title: 'Financial Overview' },
          { id: 'comp', title: 'Competitive Landscape' },
        ]}
      />,
    );
    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(2);
    expect(links[0].getAttribute('href')).toBe('#fin');
    expect(links[1].textContent).toMatch(/Competitive Landscape/);
  });

  it('marks the active id with aria-current', () => {
    render(
      <TableOfContents
        sections={[
          { id: 'fin', title: 'Financial Overview' },
          { id: 'comp', title: 'Competitive Landscape' },
        ]}
        activeId="comp"
      />,
    );
    const active = screen.getByText('Competitive Landscape').closest('a');
    expect(active?.getAttribute('aria-current')).toBe('true');
  });
});
