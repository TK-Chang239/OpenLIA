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

export function SecretaryPage({ user }: SecretaryPageProps) {
  return (
    <div className="secretary-page h-full">
      <ChatInterface
        sessionId={SESSION_ID}
        greeting={`Welcome back, ${user.display_name}.`}
        subtext="What can I help you with today?"
        chips={CHIPS}
        inputPlaceholder="Ask LIA anything..."
      />
    </div>
  );
}
