import { useEffect, useState } from 'react';
import { ChatInterface } from '../components/chat/ChatInterface';
import { getDefaultSessionForDepartment } from '../api/chat';

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

export function SecretaryPage({ user }: SecretaryPageProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDefaultSessionForDepartment('secretary')
      .then((s) => {
        if (cancelled || !s) return;
        setSessionId(s.id);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load chat session');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="secretary-page h-full p-6 text-sm text-red-600">{error}</div>
    );
  }
  if (!sessionId) {
    return <div className="secretary-page h-full" aria-busy="true" />;
  }

  return (
    <div className="secretary-page h-full">
      <ChatInterface
        sessionId={sessionId}
        greeting={`Welcome back, ${user.display_name}.`}
        subtext="What can I help you with today?"
        chips={CHIPS}
        inputPlaceholder="Ask LIA anything..."
        streamUrl="/api/departments/secretary/chat"
        bodyExtras={{ session_id: sessionId }}
      />
    </div>
  );
}
