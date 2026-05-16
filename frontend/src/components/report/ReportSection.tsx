import { BlockRenderer } from './BlockRenderer';

export interface ReportSectionProps {
  id: string;
  title: string;
  blocks: any[];
  /** Section index in the schema. Combined with the block index to build a
   *  stable `data-block-path` of "<sectionIdx>-<blockIdx>" for chart blocks
   *  so headless screenshotting (DOCX export) can find each chart. */
  sectionIndex?: number;
}

export function ReportSection({ id, title, blocks, sectionIndex }: ReportSectionProps) {
  return (
    <section id={id} className="report-section">
      <h2 className="report-section__title">{title}</h2>
      {blocks.map((b, i) => (
        <div key={i} className="report-block">
          <BlockRenderer
            block={b}
            blockPath={sectionIndex !== undefined ? `${sectionIndex}-${i}` : undefined}
          />
        </div>
      ))}
    </section>
  );
}
