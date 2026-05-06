import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ChatInterface } from "../components/chat/ChatInterface";
import { createSession, listSessions } from "../api/chat";
import { useChatHeaderRegistry } from "../layouts/ChatHeaderContext";

export interface SecretaryPageUser {
  id: string;
  display_name: string;
}

export interface SecretaryPageProps {
  user: SecretaryPageUser;
}

const CHIPS = [
  { label: "What is LIA?", value: "What is LIA?" },
  { label: "Get a quick market snapshot", value: "Get a quick market snapshot" },
  { label: "How do I use Equity Research?", value: "How do I use Equity Research?" },
  { label: "Summarize a financial term", value: "Summarize a financial term" },
];

export function SecretaryPage({ user }: SecretaryPageProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  const attachedReportId = searchParams.get("attached_report");

  const pickInitial = useCallback(async () => {
    if (attachedReportId) {
      const fresh = await createSession({
        department: "secretary",
        title: "Report follow-up",
        attached_report_id: attachedReportId,
      });
      setSessionId(fresh.id);
      // Strip the query param so a refresh doesn't re-create another session.
      const next = new URLSearchParams(searchParams);
      next.delete("attached_report");
      setSearchParams(next, { replace: true });
      return;
    }
    const r = await listSessions({ department: "secretary" });
    if (r && r.items.length > 0) {
      setSessionId(r.items[0].id);
      return;
    }
    const fresh = await createSession({ department: "secretary", title: "New chat" });
    setSessionId(fresh.id);
  }, [attachedReportId, searchParams, setSearchParams]);

  useEffect(() => {
    let cancelled = false;
    pickInitial().catch((err: unknown) => {
      if (cancelled) return;
      setError(err instanceof Error ? err.message : "Failed to load chat session");
    });
    return () => {
      cancelled = true;
    };
  }, [pickInitial]);


  const onCreate = useCallback(async () => {
    const fresh = await createSession({ department: "secretary", title: "New chat" });
    setSessionId(fresh.id);
  }, []);

  const onSelect = useCallback((id: string) => {
    setSessionId(id);
  }, []);

  const { register, clear } = useChatHeaderRegistry();
  useEffect(() => {
    if (!sessionId) {
      clear();
      return;
    }
    register({
      departmentId: "secretary",
      activeSessionId: sessionId,
      onSelect,
      onCreate,
    });
    return () => clear();
  }, [sessionId, onSelect, onCreate, register, clear]);

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
        departmentId="secretary"
      />
    </div>
  );
}
