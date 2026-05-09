import type { TimelineBlock as Block } from '../../../api/reports';

export function TimelineBlock({ title, events }: Omit<Block, 'type'>) {
  return (
    <div className="report-timeline">
      {title ? <div className="report-timeline__title">{title}</div> : null}
      <ol className="report-timeline__list">
        {events.map((event, i) => (
          <li
            key={i}
            className={`report-timeline__item${event.highlight ? ' is-highlighted' : ''}`}
          >
            <div className="report-timeline__when">{event.when}</div>
            <div className="report-timeline__what">{event.what}</div>
            {event.impact ? (
              <div className="report-timeline__impact">
                {event.impact_tag ? (
                  <span
                    className="report-timeline__impact-tag"
                    data-tone={event.impact_tag.tone ?? 'neutral'}
                  >
                    {event.impact_tag.label}
                  </span>
                ) : null}
                <span className="report-timeline__impact-text">{event.impact}</span>
              </div>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  );
}
