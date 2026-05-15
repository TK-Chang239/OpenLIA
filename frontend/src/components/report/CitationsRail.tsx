import type { Citation } from '../../api/reports';

export interface CitationsRailProps {
  citations: Citation[];
}

function composePreview(c: Citation): string {
  const parts: string[] = [c.title];
  if (c.source) parts[0] = `${parts[0]} — ${c.source}`;
  if (c.date) parts[0] = `${parts[0]} (${c.date})`;
  if (c.url) parts.push(c.url);
  return parts.join('\n');
}

export function CitationsRail({ citations }: CitationsRailProps) {
  if (citations.length === 0) return null;
  return (
    <section className="report-rail__card report-rail__citations">
      <div className="report-rail__card-label">Sources</div>
      <ol className="report-rail__citations-list">
        {citations.map((c) => {
          const preview = composePreview(c);
          const isExternal = !!c.url;
          const href = isExternal ? c.url! : `#cite-${c.id}`;
          const meta = [c.source, c.date].filter(Boolean).join(' · ');
          return (
            <li key={c.id} className="report-rail__citations-item">
              <a
                href={href}
                title={preview}
                {...(isExternal
                  ? { target: '_blank', rel: 'noreferrer noopener' }
                  : {})}
              >
                <span className="report-rail__citations-num">[{c.id}]</span>
                <span className="report-rail__citations-body">
                  <span className="report-rail__citations-title">{c.title}</span>
                  {meta ? (
                    <span className="report-rail__citations-meta">{meta}</span>
                  ) : null}
                </span>
              </a>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
