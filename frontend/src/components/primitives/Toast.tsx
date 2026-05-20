import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

export interface ToastEntry {
  readonly id: string;
  readonly title: string;
  readonly tone?: "info" | "success" | "error";
  readonly durationMs?: number;
  readonly undo?: { readonly label: string; readonly onClick: () => void };
}

interface ToastContextValue {
  readonly toasts: ReadonlyArray<ToastEntry>;
  readonly push: (entry: Omit<ToastEntry, "id">) => string;
  readonly dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const MAX_STACK = 3;

let _seq = 0;
const nextId = (): string => {
  _seq += 1;
  return `t-${Date.now()}-${_seq}`;
};

export function ToastProvider({ children }: { readonly children: ReactNode }): JSX.Element {
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const push = useCallback(
    (entry: Omit<ToastEntry, "id">) => {
      const id = nextId();
      const next: ToastEntry = { id, ...entry };
      setToasts((prev) => {
        const merged = [...prev, next];
        if (merged.length > MAX_STACK) merged.shift();
        return merged;
      });
      const ms = entry.durationMs ?? 4000;
      const timer = setTimeout(() => dismiss(id), ms);
      timers.current.set(id, timer);
      return id;
    },
    [dismiss],
  );

  useEffect(() => {
    const map = timers.current;
    return () => {
      map.forEach((t) => clearTimeout(t));
      map.clear();
    };
  }, []);

  const value = useMemo<ToastContextValue>(
    () => ({ toasts, push, dismiss }),
    [toasts, push, dismiss],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastContainer />
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // Caller may render without a provider in tests. Provide a no-op shim
    // so missing-provider crashes never blow up render trees.
    return {
      toasts: [],
      push: () => "",
      dismiss: () => {},
    };
  }
  return ctx;
}

function ToastContainer(): JSX.Element {
  const { t } = useTranslation();
  const ctx = useContext(ToastContext);
  if (!ctx) return <></>;
  return (
    <div
      role="region"
      aria-label={t("primitives.aria_notifications")}
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none"
      data-testid="toast-region"
    >
      {ctx.toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          data-testid="toast-item"
          data-tone={t.tone ?? "info"}
          className="pointer-events-auto min-w-[220px] max-w-[360px] px-3 py-2 rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-elevated] text-sm shadow flex items-center justify-between gap-3 animate-[fadeIn_120ms_ease-out]"
        >
          <span className="text-[--color-text-primary]">{t.title}</span>
          {t.undo ? (
            <button
              type="button"
              className="text-xs font-medium text-[--color-accent-primary] hover:underline"
              onClick={() => {
                t.undo?.onClick();
                ctx.dismiss(t.id);
              }}
            >
              {t.undo.label}
            </button>
          ) : null}
        </div>
      ))}
    </div>
  );
}
