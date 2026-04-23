import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { RedirectCard } from '../RedirectCard';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderCard(props?: Partial<React.ComponentProps<typeof RedirectCard>>) {
  return render(
    <MemoryRouter>
      <RedirectCard
        department="equity_research"
        reason="Full initiation report needed"
        prefill="AAPL"
        {...props}
      />
    </MemoryRouter>,
  );
}

describe('RedirectCard', () => {
  it('renders the explanation and a primary CTA for the target department', () => {
    renderCard();
    expect(screen.getByText(/Full initiation report needed/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Go to Equity Research/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Stay here/i })).toBeInTheDocument();
  });

  it('navigates to the department with the prefill as a query parameter', () => {
    mockNavigate.mockClear();
    renderCard();
    fireEvent.click(screen.getByRole('button', { name: /Go to Equity Research/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/equity-research?q=AAPL');
  });

  it('omits the query parameter when no prefill is given', () => {
    mockNavigate.mockClear();
    renderCard({ prefill: undefined });
    fireEvent.click(screen.getByRole('button', { name: /Go to Equity Research/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/equity-research');
  });

  it('hides the card when Stay here is clicked', () => {
    renderCard();
    fireEvent.click(screen.getByRole('button', { name: /Stay here/i }));
    expect(screen.queryByRole('button', { name: /Go to Equity Research/i })).toBeNull();
  });
});
