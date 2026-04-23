import { useState } from 'react';

import type { ReportSchema } from '../../api/reports';
import { ReportCover } from './ReportCover';
import { ReportHeader } from './furniture/ReportHeader';
import { ReportFooter } from './furniture/ReportFooter';
import { ReportSection } from './ReportSection';
import { ReportSkeleton } from './ReportSkeleton';
import { ScrollTracker } from './furniture/ScrollTracker';
import { TableOfContents } from './TableOfContents';

export type ReportTheme = 'light' | 'dark';

export interface ReportRendererProps {
  schema?: ReportSchema;
  loading?: boolean;
  sectionTitles?: string[];
  theme?: ReportTheme;
}

export function ReportRenderer({
  schema,
  loading = false,
  sectionTitles = [],
  theme = 'light',
}: ReportRendererProps) {
  const [activeId, setActiveId] = useState<string | undefined>();
  const titles = schema?.sections?.map((s) => s.title) ?? sectionTitles;

  if (loading || !schema) {
    return (
      <div data-report-theme={theme} className="report">
        <ReportSkeleton sectionTitles={titles} />
      </div>
    );
  }

  const furniture = schema.page_furniture;
  const tocSections = schema.sections.map((s) => ({ id: s.id, title: s.title }));

  return (
    <div data-report-theme={theme} className="report">
      {furniture ? (
        <ReportHeader left={furniture.header.left} right={furniture.header.right} />
      ) : null}
      <div className="report__body">
        <aside className="report__toc">
          <TableOfContents sections={tocSections} activeId={activeId} />
        </aside>
        <main className="report__main">
          <ReportCover cover={schema.cover} />
          <ScrollTracker
            sectionIds={tocSections.map((t) => t.id)}
            onActiveId={setActiveId}
          />
          {schema.sections.map((s) => (
            <ReportSection key={s.id} id={s.id} title={s.title} blocks={s.blocks as any[]} />
          ))}
        </main>
      </div>
      {furniture ? (
        <ReportFooter
          left={furniture.footer.left}
          center={furniture.footer.center}
          right={furniture.footer.right}
          disclaimer={furniture.disclaimer}
        />
      ) : null}
    </div>
  );
}
