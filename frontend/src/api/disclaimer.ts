export interface DisclaimerPayload {
  text: string;
  version: string;
}

export interface DisclaimerStatus {
  current_version: string;
  accepted: boolean;
  accepted_version: string | null;
}

const PERSONAL_KEY = "lia_disclaimer_accepted";

export async function fetchDisclaimer(): Promise<DisclaimerPayload> {
  const r = await fetch("/api/disclaimer");
  if (!r.ok) throw new Error("disclaimer_fetch_failed");
  return r.json() as Promise<DisclaimerPayload>;
}

export async function fetchDisclaimerStatus(
  mode: "personal" | "company",
): Promise<DisclaimerStatus> {
  if (mode === "personal") {
    const raw = localStorage.getItem(PERSONAL_KEY);
    const current = (await fetchDisclaimer()).version;
    if (!raw)
      return { current_version: current, accepted: false, accepted_version: null };
    const parsed = JSON.parse(raw) as { version: string; accepted_at: string };
    return {
      current_version: current,
      accepted: parsed.version === current,
      accepted_version: parsed.version,
    };
  }
  const r = await fetch("/api/disclaimer/status");
  if (!r.ok) throw new Error("disclaimer_status_failed");
  return r.json() as Promise<DisclaimerStatus>;
}

export async function acceptDisclaimer(
  mode: "personal" | "company",
  version: string,
): Promise<void> {
  if (mode === "personal") {
    localStorage.setItem(
      PERSONAL_KEY,
      JSON.stringify({ version, accepted_at: new Date().toISOString() }),
    );
    return;
  }
  const r = await fetch("/api/disclaimer/accept", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ version }),
  });
  if (!r.ok) throw new Error("disclaimer_accept_failed");
}
