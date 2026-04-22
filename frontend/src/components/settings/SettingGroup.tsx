import React from 'react';

interface Props {
  title: string;
  description?: string;
  children: React.ReactNode;
}

export function SettingGroup({ title, description, children }: Props): JSX.Element {
  return (
    <section className="space-y-3 border-b border-border pb-6 last:border-b-0">
      <header>
        <h3 className="text-base font-semibold text-fg">{title}</h3>
        {description ? <p className="mt-1 text-sm text-fg-muted">{description}</p> : null}
      </header>
      <div className="space-y-3">{children}</div>
    </section>
  );
}
