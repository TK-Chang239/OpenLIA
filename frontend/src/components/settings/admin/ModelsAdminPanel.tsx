export function ModelsAdminPanel(): JSX.Element {
  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-base font-semibold text-text-primary">Server-wide models</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Register, test, or remove models for each capability tier. These become the defaults for all users.
        </p>
      </header>
      <p className="text-sm text-text-secondary">
        Server-wide model CRUD is not yet wired up in this panel. Use the setup wizard to edit the roster.
      </p>
    </div>
  );
}
