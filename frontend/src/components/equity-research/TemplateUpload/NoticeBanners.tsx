import type { TemplateLoadNotice } from "../../../api/report-templates";

interface Props {
  notices: TemplateLoadNotice[];
}

export function NoticeBanners({ notices }: Props) {
  if (notices.length === 0) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      {notices.map((notice, i) => (
        <div
          key={`${notice.kind}-${notice.key}-${i}`}
          className={
            notice.kind === "reserved_key" ? "reserved-key-banner" : "unknown-key-banner"
          }
          style={{
            padding: "0.75rem",
            background: "var(--color-warning-bg, #fffbeb)",
            border: "1px solid var(--color-warning-border, #fcd34d)",
            borderRadius: "0.375rem",
            fontSize: "0.875rem",
          }}
        >
          <strong>{notice.key}</strong> {notice.message}
        </div>
      ))}
    </div>
  );
}
