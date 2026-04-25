import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../components/chat/ChatInterface', () => ({
  ChatInterface: ({ greeting, subtext, chips, inputPlaceholder }: any) => (
    <div data-testid="chat-interface">
      <h1>{greeting}</h1>
      <p>{subtext}</p>
      <ul>
        {chips.map((c: { label: string; value: string }) => (
          <li key={c.value}>
            <button type="button">{c.label}</button>
          </li>
        ))}
      </ul>
      <span data-testid="placeholder">{inputPlaceholder}</span>
    </div>
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
    expect(
      screen.getAllByRole('button', {
        name: /^(What is LIA|Get a quick market snapshot|How do I use Equity Research|Summarize).*/,
      }),
    ).not.toHaveLength(0);
  });

  it('uses the spec-mandated input placeholder', () => {
    renderPage();
    expect(screen.getByTestId('placeholder')).toHaveTextContent(/Ask LIA anything/);
  });
});
