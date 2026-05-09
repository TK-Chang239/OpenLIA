import type { CalloutGridBlock as Block } from '../../../api/reports';

export function CalloutGridBlock({ columns = 3, items }: Omit<Block, 'type'>) {
  return (
    <div
      className="report-callout-grid"
      style={{ display: 'grid', gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`, gap: 12 }}
    >
      {items.map((item, i) => (
        <div key={i} className="report-callout-card">
          {item.eyebrow ? <div className="report-callout-card__eyebrow">{item.eyebrow}</div> : null}
          <div className="report-callout-card__title">{item.title}</div>
          <div className="report-callout-card__description">{item.description}</div>
        </div>
      ))}
    </div>
  );
}
