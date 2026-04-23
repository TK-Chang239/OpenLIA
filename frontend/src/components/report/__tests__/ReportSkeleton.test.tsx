import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { ReportSkeleton } from '../ReportSkeleton';

describe('ReportSkeleton', () => {
  it('renders one placeholder block per section title', () => {
    const { container } = render(
      <ReportSkeleton sectionTitles={['Cover', 'Financial', 'Competitive']} />,
    );
    expect(container.querySelectorAll('.report-skeleton__section')).toHaveLength(3);
  });
});
