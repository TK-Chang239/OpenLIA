export interface SupportedCapability {
  id: string;
  summary: string;
}

export interface UnsupportedCapability {
  id: string;
  summary: string;
  planned_in: string | null;
  user_message: string;
}

export interface CapabilityManifest {
  engine_version: string;
  dev_mode: boolean;
  supported: SupportedCapability[];
  unsupported: UnsupportedCapability[];
}

export async function fetchCapabilities(): Promise<CapabilityManifest> {
  const r = await fetch("/api/capabilities");
  if (!r.ok) throw new Error(`failed to fetch capabilities: ${r.status}`);
  return r.json();
}
