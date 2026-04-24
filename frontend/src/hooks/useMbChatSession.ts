import { useEffect, useState } from "react";

import { resolveChatSession } from "../api/morning-briefing";

export function useMbChatSession() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    resolveChatSession()
      .then(({ session_id }) => {
        if (!cancelled) setSessionId(session_id);
      })
      .catch((e) => {
        if (!cancelled) setError(e as Error);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { sessionId, error };
}
