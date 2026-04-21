interface PagePlaceholderProps {
  title: string;
}

export function PagePlaceholder({ title }: PagePlaceholderProps): JSX.Element {
  return (
    <section className="p-8">
      <h1 className="text-2xl font-semibold text-text-primary">{title}</h1>
      <p className="mt-2 text-sm text-text-secondary">
        Page body arrives in a later plan.
      </p>
    </section>
  );
}
