export interface GuardrailEvent {
  id: string;
  created_at: string;
  session_id: string;
  user_id: string | null;
  department_id: string;
  event_type: "persona_refusal" | "tripwire_flag";
  category: string;
  action_taken: "replaced" | "warned" | "logged";
  tripwire_pattern: string | null;
  response_excerpt: string;
  model_ref: string | null;
}

export async function listGuardrailEvents(params: {
  since_days?: number;
  category?: string;
  department_id?: string;
}): Promise<GuardrailEvent[]> {
  const qs = new URLSearchParams();
  if (params.since_days) qs.set("since_days", String(params.since_days));
  if (params.category) qs.set("category", params.category);
  if (params.department_id) qs.set("department_id", params.department_id);
  const r = await fetch(`/api/admin/guardrail-events?${qs}`);
  if (!r.ok) throw new Error("guardrail_events_fetch_failed");
  return (await r.json()).items;
}

export async function wipeGuardrailEvents(): Promise<number> {
  const r = await fetch("/api/admin/guardrail-events", { method: "DELETE" });
  if (!r.ok) throw new Error("guardrail_events_wipe_failed");
  return (await r.json()).deleted;
}
