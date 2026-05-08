import type { BulletListBlock as Block } from '../../../api/reports';

export function BulletListBlock({ items, tone = 'default' }: Omit<Block, 'type'>) {
  return (
    <ul className="report-bullet-list" data-tone={tone}>
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}
