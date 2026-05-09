import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export interface ChatHeaderValue {
  departmentId: string;
  activeSessionId: string | null;
  /** Title of the active session. Rendered as an appended breadcrumb
   *  segment with a chevron that opens the history popover. */
  chatTitle: string | null;
  /** Switch the page to a session picked from the popover. */
  onSelect: (sessionId: string) => void;
  /** Create a fresh session and switch to it. The handler owns the
   *  ``createSession`` call so the page can keep its state in sync. */
  onCreate: () => void;
}

interface RegistryShape {
  value: ChatHeaderValue | null;
  register: (value: ChatHeaderValue) => void;
  clear: () => void;
}

const ChatHeaderRegistry = createContext<RegistryShape | null>(null);

/** Mounted high in the layout (above ``TopBar``). Pages call ``register``
 *  via ``useRegisterChatHeader`` from inside their own subtree, and the
 *  ``TopBar`` reads ``value`` to render the dropdown + new-chat controls. */
export function ChatHeaderProvider({ children }: { children: ReactNode }): JSX.Element {
  const [value, setValue] = useState<ChatHeaderValue | null>(null);
  const register = useCallback((next: ChatHeaderValue) => setValue(next), []);
  const clear = useCallback(() => setValue(null), []);
  const ctx = useMemo<RegistryShape>(
    () => ({ value, register, clear }),
    [value, register, clear],
  );
  return <ChatHeaderRegistry.Provider value={ctx}>{children}</ChatHeaderRegistry.Provider>;
}

export function useChatHeader(): ChatHeaderValue | null {
  return useContext(ChatHeaderRegistry)?.value ?? null;
}

/** Pages call this to publish their session state to the layout TopBar.
 *  Pass ``null`` to unregister (e.g. on unmount). */
export function useChatHeaderRegistry(): RegistryShape {
  const ctx = useContext(ChatHeaderRegistry);
  if (!ctx) {
    return { value: null, register: () => undefined, clear: () => undefined };
  }
  return ctx;
}
