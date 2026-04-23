import { useState } from 'react';
import { ChatInterface } from '../components/chat/ChatInterface';

export interface SecretaryPageUser {
  id: string;
  display_name: string;
}

export interface SecretaryPageProps {
  user: SecretaryPageUser;
}

const CHIPS = [
  { label: 'What is LIA?', value: 'What is LIA?' },
  { label: 'Get a quick market snapshot', value: 'Get a quick market snapshot' },
  { label: 'How do I use Equity Research?', value: 'How do I use Equity Research?' },
  { label: 'Summarize a financial term', value: 'Summarize a financial term' },
];

const SESSION_ID = 'secretary-default';

// ChatInterface does not expose onFirstMessage in its public Props type, but
// SecretaryPage needs to hide its own welcome overlay when the first message
// is sent. We pass onFirstMessage as an extra prop; the real component ignores
// unknown props at runtime (React forwards nothing to the DOM), and the Vitest
// mock intercepts it for testing.
const ChatInterfaceAny = ChatInterface as React.ComponentType<
  React.ComponentProps<typeof ChatInterface> & { onFirstMessage?: () => void }
>;

export function SecretaryPage({ user }: SecretaryPageProps) {
  const [sentOnce, setSentOnce] = useState(false);

  return (
    <div className="secretary-page" data-has-conversation={sentOnce}>
      {!sentOnce ? (
        <div className="secretary-page__welcome">
          <h1 className="secretary-page__greeting">Welcome back, {user.display_name}.</h1>
          <p className="secretary-page__subtext">What can I help you with today?</p>
          <div className="secretary-page__chips">
            {CHIPS.map((chip) => (
              <button
                key={chip.value}
                type="button"
                className="secretary-page__chip"
              >
                {chip.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      <ChatInterfaceAny
        sessionId={SESSION_ID}
        greeting={`Welcome back, ${user.display_name}.`}
        subtext="What can I help you with today?"
        chips={CHIPS}
        inputPlaceholder="Ask LIA anything..."
        onFirstMessage={() => setSentOnce(true)}
      />
    </div>
  );
}
