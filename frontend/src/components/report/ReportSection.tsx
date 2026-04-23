import { BlockRenderer } from './BlockRenderer';

export interface ReportSectionProps {
  id: string;
  title: string;
  blocks: any[];
}

export function ReportSection({ id, title, blocks }: ReportSectionProps) {
  return (
    <section id={id} className="report-section">
      <h2 className="report-section__title">{title}</h2>
      {blocks.map((b, i) => (
        <div key={i} className="report-block">
          <BlockRenderer block={b} />
        </div>
      ))}
    </section>
  );
}
