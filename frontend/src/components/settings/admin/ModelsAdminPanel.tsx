import React from 'react';
import { TierSlotCard } from '../../../setup/steps/TierSlotCard';

const TIERS = ['everyday', 'quick', 'thinking', 'long_context'] as const;

export function ModelsAdminPanel(): JSX.Element {
  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-base font-semibold text-text-primary">Server-wide models</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Register, test, or remove models for each capability tier. These become the defaults for all users.
        </p>
      </header>
      <div className="grid gap-4">
        {TIERS.map((t) => (
          <TierSlotCard key={t} tier={t} mode="admin" />
        ))}
      </div>
    </div>
  );
}
