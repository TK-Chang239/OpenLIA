import { useCallback, useEffect, useMemo, useState } from 'react';
import type { JSX } from 'react';
import { deleteConstruct, listConstructs, type Construct } from '../../api/graph';
import { ApiError } from '../../api/_request';
import { useToast } from '../primitives/Toast';
import { ConstructCard } from './ConstructCard';

interface EntityGroup {
  entityId: string;
  label: string;
  items: Construct[];
}

function formatEntityLabel(entityId: string): string {
  const ix = entityId.indexOf(':');
  if (ix < 0) return entityId;
  const kind = entityId.slice(0, ix);
  const value = entityId.slice(ix + 1);
  return `${value} (${kind})`;
}

function groupByEntity(items: readonly Construct[]): EntityGroup[] {
  const map = new Map<string, Construct[]>();
  for (const item of items) {
    const bucket = map.get(item.entity_id);
    if (bucket) bucket.push(item);
    else map.set(item.entity_id, [item]);
  }
  const groups: EntityGroup[] = [];
  for (const [entityId, bucketItems] of map.entries()) {
    groups.push({
      entityId,
      label: formatEntityLabel(entityId),
      items: bucketItems,
    });
  }
  groups.sort((a, b) => a.label.localeCompare(b.label));
  return groups;
}

export function ConstructsList(): JSX.Element {
  const [items, setItems] = useState<Construct[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyIds, setBusyIds] = useState<ReadonlySet<string>>(new Set());
  const toast = useToast();

  useEffect(() => {
    let cancelled = false;
    setError(null);
    listConstructs()
      .then((r) => {
        if (cancelled) return;
        setItems(r.items);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const msg = e instanceof ApiError ? e.message : 'Failed to load constructs';
        setError(msg);
        setItems([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const setBusy = useCallback((id: string, on: boolean) => {
    setBusyIds((prev) => {
      const next = new Set(prev);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  }, []);

  const handleDelete = useCallback(
    async (id: string) => {
      if (items === null) return;
      const previous = items;
      const optimistic = items.filter((c) => c.id !== id);
      setItems(optimistic);
      setBusy(id, true);
      try {
        await deleteConstruct(id);
      } catch (e: unknown) {
        setItems(previous);
        const msg = e instanceof ApiError ? e.message : 'Failed to delete construct';
        toast.push({ title: msg, tone: 'error' });
      } finally {
        setBusy(id, false);
      }
    },
    [items, setBusy, toast],
  );

  const groups = useMemo(() => (items ? groupByEntity(items) : []), [items]);

  if (items === null) {
    return <p className="text-sm text-text-secondary">Loading...</p>;
  }
  if (error && items.length === 0) {
    return (
      <div
        role="alert"
        className="rounded-md border border-feedback-error/20 bg-feedback-error/10 px-3 py-2 text-sm text-feedback-error"
      >
        {error}
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <p data-testid="constructs-empty" className="text-sm text-text-secondary">
        No confirmed beliefs yet.
      </p>
    );
  }
  return (
    <div className="space-y-6" data-testid="constructs-list">
      {groups.map((g) => (
        <section
          key={g.entityId}
          data-testid="construct-group"
          data-entity-id={g.entityId}
          className="space-y-3"
        >
          <h2 className="font-mono text-[11px] uppercase tracking-wide text-text-tertiary">
            {g.label}
          </h2>
          <div className="space-y-3">
            {g.items.map((c) => (
              <ConstructCard
                key={c.id}
                construct={c}
                onDelete={handleDelete}
                busy={busyIds.has(c.id)}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
