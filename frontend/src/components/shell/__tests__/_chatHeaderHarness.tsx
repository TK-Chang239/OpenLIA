import { useEffect, type JSX, type ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";

import {
  ChatHeaderProvider,
  useChatHeaderRegistry,
  type ChatHeaderValue,
} from "../../../layouts/ChatHeaderContext";

function Register({ value, children }: { value: ChatHeaderValue; children: ReactNode }): JSX.Element {
  const { register, clear } = useChatHeaderRegistry();
  useEffect(() => {
    register(value);
    return () => clear();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [register, clear, value.generating, value.chatTitle, value.activeSessionId]);
  return <>{children}</>;
}

export function ChatHeaderRegistryTestHarness({
  value,
  children,
}: {
  value: ChatHeaderValue;
  children: ReactNode;
}): JSX.Element {
  return (
    <MemoryRouter>
      <ChatHeaderProvider>
        <Register value={value}>{children}</Register>
      </ChatHeaderProvider>
    </MemoryRouter>
  );
}
