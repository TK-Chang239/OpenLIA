import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const listProposals = vi.fn();
const acceptProposal = vi.fn();
const dismissProposal = vi.fn();
const listConstructs = vi.fn();
const deleteConstruct = vi.fn();

vi.mock('../../api/graph', () => ({
  listProposals: (...a: unknown[]) => listProposals(...a),
  acceptProposal: (...a: unknown[]) => acceptProposal(...a),
  dismissProposal: (...a: unknown[]) => dismissProposal(...a),
  listConstructs: (...a: unknown[]) => listConstructs(...a),
  deleteConstruct: (...a: unknown[]) => deleteConstruct(...a),
}));

import { MemoryPage } from '../MemoryPage';
import { ToastProvider } from '../../components/primitives/Toast';

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/memory']}>
      <ToastProvider>
        <MemoryPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

const SAMPLE_PROPOSAL = {
  id: 'p1',
  kind: 'user_construct',
  payload: {
    construct_kind: 'position',
    statement: 'long NVDA at $400',
    entity_kind: 'ticker',
    entity_value: 'NVDA',
    source_excerpt: 'I am long NVDA at $400',
  },
  status: 'pending',
  created_at: '2026-05-09T00:00:00Z',
};

const SAMPLE_CONSTRUCT = {
  id: 'c1',
  kind: 'position',
  status: 'confirmed',
  statement: 'long NVDA at $400',
  entity_id: 'ticker:NVDA',
  created_at: '2026-05-09T00:00:00Z',
  updated_at: '2026-05-09T00:00:00Z',
  provenance: { source_excerpt: 'I am long NVDA at $400' },
};

const SAMPLE_CONSTRUCT_2 = {
  id: 'c2',
  kind: 'thesis',
  status: 'confirmed',
  statement: 'AAPL services margin will expand',
  entity_id: 'ticker:AAPL',
  created_at: '2026-05-09T00:00:00Z',
  updated_at: '2026-05-09T00:00:00Z',
  provenance: null,
};

describe('MemoryPage — pending proposals tab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listProposals.mockResolvedValue({ items: [] });
    listConstructs.mockResolvedValue({ items: [] });
  });

  it('shows empty state when no proposals', async () => {
    renderPage();
    expect(await screen.findByTestId('proposals-empty')).toBeInTheDocument();
    expect(screen.getByText(/No pending proposals/i)).toBeInTheDocument();
  });

  it('renders a proposal row with summary and excerpt toggle', async () => {
    listProposals.mockResolvedValueOnce({ items: [SAMPLE_PROPOSAL] });
    renderPage();
    expect(await screen.findByText('long NVDA at $400')).toBeInTheDocument();
    expect(screen.queryByTestId('proposal-source-excerpt')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Show source/i }));
    expect(screen.getByTestId('proposal-source-excerpt')).toHaveTextContent(
      'I am long NVDA at $400',
    );
  });

  it('accept removes row optimistically and calls API', async () => {
    listProposals.mockResolvedValueOnce({ items: [SAMPLE_PROPOSAL] });
    acceptProposal.mockResolvedValueOnce({});
    renderPage();
    await screen.findByText('long NVDA at $400');
    fireEvent.click(screen.getByRole('button', { name: /^Accept$/ }));
    await waitFor(() => expect(acceptProposal).toHaveBeenCalledWith('p1'));
    expect(screen.queryByText('long NVDA at $400')).not.toBeInTheDocument();
    expect(await screen.findByTestId('proposals-empty')).toBeInTheDocument();
  });

  it('accept restores row when API errors', async () => {
    listProposals.mockResolvedValueOnce({ items: [SAMPLE_PROPOSAL] });
    acceptProposal.mockRejectedValueOnce(new Error('boom'));
    renderPage();
    await screen.findByText('long NVDA at $400');
    fireEvent.click(screen.getByRole('button', { name: /^Accept$/ }));
    await waitFor(() => expect(acceptProposal).toHaveBeenCalled());
    expect(await screen.findByText('long NVDA at $400')).toBeInTheDocument();
  });

  it('dismiss removes row and calls API', async () => {
    listProposals.mockResolvedValueOnce({ items: [SAMPLE_PROPOSAL] });
    dismissProposal.mockResolvedValueOnce({ ok: true });
    renderPage();
    await screen.findByText('long NVDA at $400');
    fireEvent.click(screen.getByRole('button', { name: /^Dismiss$/ }));
    await waitFor(() => expect(dismissProposal).toHaveBeenCalledWith('p1'));
    expect(screen.queryByText('long NVDA at $400')).not.toBeInTheDocument();
  });
});

describe('MemoryPage — confirmed beliefs tab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listProposals.mockResolvedValue({ items: [] });
    listConstructs.mockResolvedValue({ items: [] });
  });

  it('shows empty state on the confirmed tab', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('tab', { name: /Confirmed beliefs/i }));
    expect(await screen.findByTestId('constructs-empty')).toBeInTheDocument();
    expect(screen.getByText(/No confirmed beliefs yet/i)).toBeInTheDocument();
  });

  it('renders constructs grouped by entity', async () => {
    listConstructs.mockResolvedValueOnce({
      items: [SAMPLE_CONSTRUCT, SAMPLE_CONSTRUCT_2],
    });
    renderPage();
    fireEvent.click(screen.getByRole('tab', { name: /Confirmed beliefs/i }));
    await screen.findByText('long NVDA at $400');
    const groups = screen.getAllByTestId('construct-group');
    expect(groups).toHaveLength(2);
    const entityIds = groups.map((g) => g.getAttribute('data-entity-id'));
    expect(entityIds).toContain('ticker:NVDA');
    expect(entityIds).toContain('ticker:AAPL');
  });

  it('delete construct removes row optimistically and calls API', async () => {
    listConstructs.mockResolvedValueOnce({ items: [SAMPLE_CONSTRUCT] });
    deleteConstruct.mockResolvedValueOnce(undefined);
    renderPage();
    fireEvent.click(screen.getByRole('tab', { name: /Confirmed beliefs/i }));
    await screen.findByText('long NVDA at $400');
    fireEvent.click(screen.getByRole('button', { name: /Delete construct c1/ }));
    await waitFor(() => expect(deleteConstruct).toHaveBeenCalledWith('c1'));
    expect(screen.queryByText('long NVDA at $400')).not.toBeInTheDocument();
    expect(await screen.findByTestId('constructs-empty')).toBeInTheDocument();
  });

  it('delete restores row on error', async () => {
    listConstructs.mockResolvedValueOnce({ items: [SAMPLE_CONSTRUCT] });
    deleteConstruct.mockRejectedValueOnce(new Error('boom'));
    renderPage();
    fireEvent.click(screen.getByRole('tab', { name: /Confirmed beliefs/i }));
    await screen.findByText('long NVDA at $400');
    fireEvent.click(screen.getByRole('button', { name: /Delete construct c1/ }));
    await waitFor(() => expect(deleteConstruct).toHaveBeenCalled());
    expect(await screen.findByText('long NVDA at $400')).toBeInTheDocument();
  });

  it('Why? reveal shows provenance excerpt', async () => {
    listConstructs.mockResolvedValueOnce({ items: [SAMPLE_CONSTRUCT] });
    renderPage();
    fireEvent.click(screen.getByRole('tab', { name: /Confirmed beliefs/i }));
    await screen.findByText('long NVDA at $400');
    expect(screen.queryByTestId('construct-source-excerpt')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^Why\?$/ }));
    expect(screen.getByTestId('construct-source-excerpt')).toHaveTextContent(
      'I am long NVDA at $400',
    );
  });
});
