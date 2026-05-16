import type { Citation } from '../../api/reports';

export const SOURCES_SECTION_ID = 'sources';

export interface CitationsSectionProps {
  citations: Citation[];
}

export function displayCitationTitle(c: Citation): string {
  if (c.title) return c.title;
  if (c.url) {
    try {
      const u = new URL(c.url.startsWith('http') ? c.url : `https://${c.url}`);
      const host = u.hostname.replace(/^www\./, '');
      const path = u.pathname.replace(/\/$/, '');
      return `${host}${path}`;
    } catch {
      return c.url;
    }
  }
  if (c.source && c.date) return `${c.source} · ${c.date}`;
  if (c.source) return c.source;
  return '(source)';
}

export function CitationsSection({ citations }: CitationsSectionProps) {
  if (!citations.length) return null;
  return (
    <section id={SOURCES_SECTION_ID} className="report-section report-section--sources">
      <h2 className="report-section__title">Sources &amp; Disclosures</h2>
      <ol className="report-citations">
        {citations.map((c) => {
          const label = displayCitationTitle(c);
          return (
            <li key={c.id} id={`cite-${c.id}`} className="report-citations__item">
              <span className="report-citations__num">[{c.id}]</span>
              <div className="report-citations__body">
                <div className="report-citations__title">
                  {c.url ? (
                    <a href={c.url} target="_blank" rel="noreferrer noopener">{label}</a>
                  ) : (
                    label
                  )}
                </div>
                {(c.source || c.date) ? (
                  <div className="report-citations__meta">
                    {c.source ? <span>{c.source}</span> : null}
                    {c.source && c.date ? <span> · </span> : null}
                    {c.date ? <span>{c.date}</span> : null}
                  </div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
