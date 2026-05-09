import type { Citation } from '../../api/reports';

export const SOURCES_SECTION_ID = 'sources';

export interface CitationsSectionProps {
  citations: Citation[];
}

export function CitationsSection({ citations }: CitationsSectionProps) {
  if (!citations.length) return null;
  return (
    <section id={SOURCES_SECTION_ID} className="report-section report-section--sources">
      <h2 className="report-section__title">Sources &amp; Disclosures</h2>
      <ol className="report-citations">
        {citations.map((c) => (
          <li key={c.id} id={`cite-${c.id}`} className="report-citations__item">
            <span className="report-citations__num">[{c.id}]</span>
            <div className="report-citations__body">
              <div className="report-citations__title">
                {c.url ? (
                  <a href={c.url} target="_blank" rel="noreferrer noopener">{c.title}</a>
                ) : (
                  c.title
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
        ))}
      </ol>
    </section>
  );
}
