import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReportHeader } from '../ReportHeader';
import { ReportFooter } from '../ReportFooter';

describe('ReportHeader', () => {
  it('renders header left and right text', () => {
    render(<ReportHeader left="OpenLIA" right="Equity Research" />);
    expect(screen.getByText('OpenLIA')).toBeInTheDocument();
    expect(screen.getByText('Equity Research')).toBeInTheDocument();
  });
});

describe('ReportFooter', () => {
  it('renders footer columns and disclaimer', () => {
    render(
      <ReportFooter
        left="Generated Apr 11, 2026"
        center="Page {page}"
        right="For internal use only"
        disclaimer="Not advice."
      />,
    );
    expect(screen.getByText(/Generated/)).toBeInTheDocument();
    expect(screen.getByText('For internal use only')).toBeInTheDocument();
    expect(screen.getByText('Not advice.')).toBeInTheDocument();
  });
});
