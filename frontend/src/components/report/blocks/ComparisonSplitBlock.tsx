import type { ComparisonSplitBlock as Block, ComparisonColumn } from '../../../api/reports';

function Column({ column, side }: { column: ComparisonColumn; side: 'left' | 'right' }) {
  const tone = column.tone ?? 'neutral';
  return (
    <div className="report-comparison-split__col" data-tone={tone} data-side={side}>
      <div className="report-comparison-split__title">{column.title}</div>
      <ul className="report-comparison-split__items">
        {column.items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export function ComparisonSplitBlock({ left, right }: Omit<Block, 'type'>) {
  return (
    <div
      className="report-comparison-split"
      style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}
    >
      <Column column={left} side="left" />
      <Column column={right} side="right" />
    </div>
  );
}
