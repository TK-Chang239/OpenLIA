import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../components/chat/ChatInterface', () => ({
  ChatInterface: ({ onFirstMessage }: any) => (
    <button data-testid="send" onClick={() => onFirstMessage?.('hi')}>
      send
    </button>
  ),
}));

import { SecretaryPage } from '../SecretaryPage';

function renderPage() {
  return render(
    <MemoryRouter>
      <SecretaryPage user={{ id: 'u1', display_name: 'Alex' }} />
    </MemoryRouter>,
  );
}

describe('SecretaryPage', () => {
  it('shows a personalized welcome state on first load', () => {
    renderPage();
    expect(screen.getByText(/Welcome back, Alex/)).toBeInTheDocument();
    expect(screen.getByText(/What can I help you with today/)).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /^(What is LIA|Get a quick market snapshot|How do I use Equity Research|Summarize).*/ })).not.toHaveLength(0);
  });

  it('hides the welcome state once a message has been sent', () => {
    renderPage();
    fireEvent.click(screen.getByTestId('send'));
    expect(screen.queryByText(/Welcome back, Alex/)).toBeNull();
  });
});
