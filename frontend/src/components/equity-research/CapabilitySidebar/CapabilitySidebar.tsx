import type { CapabilityManifest } from "../../../api/capabilities";

interface Props {
  manifest: CapabilityManifest;
}

export function CapabilitySidebar({ manifest }: Props) {
  return (
    <aside className="flex flex-col gap-3 text-sm text-[--color-text-secondary]">
      <div className="font-medium text-[--color-text-primary]">
        Engine v{manifest.engine_version}
      </div>

      <details open>
        <summary className="cursor-pointer font-medium text-[--color-text-primary] select-none">
          Supported
        </summary>
        <ul className="mt-2 flex flex-col gap-1 pl-3">
          {manifest.supported.map((cap) => (
            <li key={cap.id} className="leading-snug">
              <span className="font-mono text-xs text-[--color-text-muted] mr-1">
                {cap.id}
              </span>
              {cap.summary}
            </li>
          ))}
        </ul>
      </details>

      <details open>
        <summary className="cursor-pointer font-medium text-[--color-text-primary] select-none">
          Not yet supported
        </summary>
        <ul className="mt-2 flex flex-col gap-1 pl-3">
          {manifest.unsupported.map((cap) => (
            <li key={cap.id} className="leading-snug">
              <span className="font-mono text-xs text-[--color-text-muted] mr-1">
                {cap.id}
              </span>
              {cap.user_message}
              {cap.planned_in != null && (
                <em className="ml-1 text-[--color-text-muted]">
                  planned for v{cap.planned_in}
                </em>
              )}
            </li>
          ))}
        </ul>
      </details>
    </aside>
  );
}
