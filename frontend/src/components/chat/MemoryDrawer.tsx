import { useCallback, useEffect, useState } from "react";
import { X } from "lucide-react";
import {
  acceptProposal,
  dismissProposal,
  listProposals,
  type Proposal,
} from "../../api/graph";

interface Props {
  /** Whether the slide-in panel is open. Controlled by the parent so the
   *  toggle button can live in the chat header. */
  open: boolean;
  /** Called when the user clicks the close affordance inside the drawer. */
  onClose: () => void;
  /** Pre-rendered ``## Memory`` markdown injected into the system prompt
   *  this turn. ``null`` means retrieval ran but found nothing.
   *  ``undefined`` means the chat.memory_block event hasn't arrived yet. */
  memoryBlock: string | null | undefined;
  /** Memory page route to deep-link to from the footer. Falls back to a
   *  no-op when the slice 14 Memory page hasn't shipped yet. */
  memoryPagePath?: string | null;
}

type Status = "idle" | "loading" | "loaded" | "error";

export function MemoryDrawer({
  open,
  onClose,
  memoryBlock,
  memoryPagePath = "/memory",
}: Props): JSX.Element | null {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setStatus("loading");
    setErrorMsg(null);
    try {
      const r = await listProposals("pending");
      setProposals(r.items);
      setStatus("loaded");
    } catch (err) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "Failed to load proposals");
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    void refresh();
  }, [open, refresh]);

  const onAccept = useCallback(
    async (id: string) => {
      try {
        await acceptProposal(id);
        setProposals((prev) => prev.filter((p) => p.id !== id));
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : "Failed to accept proposal");
      }
    },
    [],
  );

  const onDismiss = useCallback(
    async (id: string) => {
      try {
        await dismissProposal(id);
        setProposals((prev) => prev.filter((p) => p.id !== id));
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : "Failed to dismiss proposal");
      }
    },
    [],
  );

  if (!open) return null;

  return (
    <aside
      role="complementary"
      aria-label="Memory drawer"
      data-testid="memory-drawer"
      className="absolute right-0 top-0 z-30 flex h-full w-80 flex-col border-l border-[--color-border-subtle] bg-[--color-bg-base] shadow-lg"
    >
      <header className="flex items-center justify-between border-b border-[--color-border-subtle] px-4 py-3">
        <h2 className="text-sm font-semibold text-[--color-text-primary]">
          Memory
        </h2>
        <button
          type="button"
          aria-label="Close memory drawer"
          onClick={onClose}
          className="rounded-md p-1 text-[--color-text-tertiary] hover:bg-[--color-bg-hover]"
        >
          <X size={16} />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-3">
        <section aria-labelledby="memory-block-heading">
          <h3
            id="memory-block-heading"
            className="text-xs font-semibold uppercase tracking-wide text-[--color-text-tertiary]"
          >
            Injected this turn
          </h3>
          <div className="mt-2 text-sm text-[--color-text-primary]">
            {memoryBlock === undefined ? (
              <p
                data-testid="memory-block-pending"
                className="text-[--color-text-tertiary]"
              >
                Waiting for next turn...
              </p>
            ) : memoryBlock === null || memoryBlock.trim() === "" ? (
              <p
                data-testid="memory-block-empty"
                className="text-[--color-text-tertiary]"
              >
                No memory injected this turn.
              </p>
            ) : (
              <pre
                data-testid="memory-block-content"
                className="whitespace-pre-wrap break-words rounded-md bg-[--color-bg-subtle] p-3 font-mono text-xs leading-relaxed text-[--color-text-primary]"
              >
                {memoryBlock}
              </pre>
            )}
          </div>
        </section>

        <hr className="my-4 border-[--color-border-subtle]" />

        <section aria-labelledby="memory-proposals-heading">
          <div className="flex items-center justify-between">
            <h3
              id="memory-proposals-heading"
              className="text-xs font-semibold uppercase tracking-wide text-[--color-text-tertiary]"
            >
              Pending proposals
            </h3>
            <button
              type="button"
              onClick={() => void refresh()}
              className="text-xs text-[--color-accent-primary] hover:underline"
            >
              Refresh
            </button>
          </div>

          <div className="mt-2 flex flex-col gap-2">
            {status === "loading" ? (
              <p
                data-testid="memory-proposals-loading"
                className="text-xs text-[--color-text-tertiary]"
              >
                Loading proposals...
              </p>
            ) : null}
            {status === "error" && errorMsg ? (
              <p
                data-testid="memory-proposals-error"
                className="text-xs text-red-600"
              >
                {errorMsg}
              </p>
            ) : null}
            {status === "loaded" && proposals.length === 0 ? (
              <p
                data-testid="memory-proposals-empty"
                className="text-xs text-[--color-text-tertiary]"
              >
                No pending proposals.
              </p>
            ) : null}
            {proposals.map((p) => (
              <ProposalRow
                key={p.id}
                proposal={p}
                onAccept={() => void onAccept(p.id)}
                onDismiss={() => void onDismiss(p.id)}
              />
            ))}
          </div>
        </section>
      </div>

      {memoryPagePath ? (
        <footer className="border-t border-[--color-border-subtle] px-4 py-2">
          <a
            href={memoryPagePath}
            className="text-xs text-[--color-accent-primary] hover:underline"
          >
            Manage all memory →
          </a>
        </footer>
      ) : null}
    </aside>
  );
}

interface ProposalRowProps {
  proposal: Proposal;
  onAccept: () => void;
  onDismiss: () => void;
}

function ProposalRow({
  proposal,
  onAccept,
  onDismiss,
}: ProposalRowProps): JSX.Element {
  const statement =
    typeof proposal.payload.statement === "string"
      ? proposal.payload.statement
      : "(no statement)";
  const entityValue =
    typeof proposal.payload.entity_value === "string"
      ? proposal.payload.entity_value
      : null;

  return (
    <div
      data-testid="memory-proposal-row"
      className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-subtle] p-2"
    >
      <div className="text-xs uppercase tracking-wide text-[--color-text-tertiary]">
        {proposal.kind}
        {entityValue ? ` · ${entityValue}` : ""}
      </div>
      <div className="mt-1 text-sm text-[--color-text-primary]">{statement}</div>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={onAccept}
          className="rounded-md bg-[--color-accent-primary] px-2 py-1 text-xs text-white hover:bg-[--color-accent-hover]"
        >
          Accept
        </button>
        <button
          type="button"
          onClick={onDismiss}
          className="rounded-md border border-[--color-border-subtle] px-2 py-1 text-xs text-[--color-text-primary] hover:bg-[--color-bg-hover]"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}

interface ToggleProps {
  open: boolean;
  onClick: () => void;
}

/** Compact button suitable for placement inside the chat header. */
export function MemoryDrawerToggle({ open, onClick }: ToggleProps): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Toggle memory drawer"
      aria-expanded={open}
      className="rounded-md border border-[--color-border-subtle] px-2 py-1 text-xs text-[--color-text-primary] hover:bg-[--color-bg-hover]"
    >
      Memory
    </button>
  );
}
