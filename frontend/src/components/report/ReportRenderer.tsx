import { useEffect, useState } from 'react';

import type { ReportSchema } from '../../api/reports';
import { ReportCover } from './ReportCover';
import { ReportHeader } from './furniture/ReportHeader';
import { ReportFooter } from './furniture/ReportFooter';
import { ReportSection } from './ReportSection';
import { ReportSkeleton } from './ReportSkeleton';
import { ScrollTracker } from './furniture/ScrollTracker';
import { TableOfContents } from './TableOfContents';
import { RailPanel } from './RailPanel';
import { CitationsSection, SOURCES_SECTION_ID } from './CitationsSection';

export type ReportTheme = 'light' | 'dark';

function readAppTheme(): ReportTheme {
  if (typeof document === 'undefined') return 'light';
  return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
}

function useAppTheme(): ReportTheme {
  const [theme, setTheme] = useState<ReportTheme>(readAppTheme);
  useEffect(() => {
    if (typeof document === 'undefined') return;
    const root = document.documentElement;
    const sync = () => setTheme(readAppTheme());
    sync();
    const obs = new MutationObserver(sync);
    obs.observe(root, { attributes: true, attributeFilter: ['data-theme'] });
    return () => obs.disconnect();
  }, []);
  return theme;
}

export interface RelatedLink {
  title: string;
  ticker?: string | null;
  href: string;
}

export interface ReportRendererProps {
  schema?: ReportSchema;
  loading?: boolean;
  sectionTitles?: string[];
  theme?: ReportTheme;
  related?: RelatedLink[];
}

export function ReportRenderer({
  schema,
  loading = false,
  sectionTitles = [],
  theme,
  related,
}: ReportRendererProps) {
  const appTheme = useAppTheme();
  const resolvedTheme: ReportTheme = theme ?? appTheme;
  const [activeId, setActiveId] = useState<string | undefined>();
  const titles = schema?.sections?.map((s) => s.title) ?? sectionTitles;

  if (loading || !schema) {
    return (
      <div data-report-theme={resolvedTheme} className="report">
        <ReportSkeleton sectionTitles={titles} />
      </div>
    );
  }

  const furniture = schema.page_furniture;
  const citations = schema.citations ?? [];
  const tocSections = schema.sections.map((s) => ({ id: s.id, title: s.title }));
  if (citations.length) {
    tocSections.push({ id: SOURCES_SECTION_ID, title: 'Sources & Disclosures' });
  }
  const hasRail =
    !!schema.rail &&
    (!!schema.rail.verdict ||
      (schema.rail.quick_stats && schema.rail.quick_stats.length > 0) ||
      !!schema.rail.sparkline ||
      (related && related.length > 0));

  const sectionIds = tocSections.map((t) => t.id);

  return (
    <div data-report-theme={resolvedTheme} className={`report${hasRail ? ' report--3col' : ''}`}>
      {furniture ? (
        <ReportHeader left={furniture.header.left} right={furniture.header.right} />
      ) : null}
      <div className="report__body">
        <aside className="report__toc">
          <TableOfContents
            sections={tocSections}
            activeId={activeId}
            onSectionClick={setActiveId}
          />
        </aside>
        <main className="report__main">
          <ReportCover cover={schema.cover} />
          <ScrollTracker sectionIds={sectionIds} onActiveId={setActiveId} />
          {schema.sections.map((s) => (
            <ReportSection key={s.id} id={s.id} title={s.title} blocks={s.blocks as any[]} />
          ))}
          {citations.length ? <CitationsSection citations={citations} /> : null}
        </main>
        {hasRail ? (
          <aside className="report__rail">
            <RailPanel rail={schema.rail!} related={related} />
          </aside>
        ) : null}
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
