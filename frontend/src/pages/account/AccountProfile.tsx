import { useAuth } from "../../auth/AuthContext";

function Row({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex items-baseline gap-4 py-2 border-b border-border-subtle last:border-b-0">
      <dt className="w-40 text-sm text-text-secondary">{label}</dt>
      <dd className="text-sm text-text-primary">{value ?? "—"}</dd>
    </div>
  );
}

export function AccountProfile() {
  const { user, status } = useAuth();
  if (status === "loading" || !user) {
    return <p className="text-sm text-text-secondary">Loading…</p>;
  }
  return (
    <dl className="max-w-md">
      <Row label="Email" value={user.email} />
      <Row label="Display name" value={user.display_name ?? null} />
      <Row label="Role" value={user.role} />
      <Row label="User ID" value={user.id} />
    </dl>
  );
}
