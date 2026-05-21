import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { ReportSchema } from '../../api/reports';
import { ReportCover } from './ReportCover';
import { ReportHeader } from './furniture/ReportHeader';
import { ReportFooter } from './furniture/ReportFooter';
import { ReportSection } from './ReportSection';
import { ReportSkeleton } from './ReportSkeleton';
import { ScrollTracker } from './furniture/ScrollTracker';
import { TableOfContents } from './TableOfContents';
import { MetaStatsCard } from './MetaStatsCard';
import { RailPanel } from './RailPanel';
import { CitationsRail } from './CitationsRail';
import { CitationsSection, SOURCES_SECTION_ID } from './CitationsSection';
import { RunSummary } from '../equity-research/RunSummary/RunSummary';
import { VerificationHistory } from '../equity-research/VerificationHistory/VerificationHistory';

const RUN_SUMMARY_SECTION_ID = 'run_summary';
const VERIFICATION_HISTORY_SECTION_ID = 'verification_history';

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
  reportId?: string | null;
  // v2.2 engine: when true and schema.verification_history is set, the
  // dev-only diagnostics table renders. Default false. The backend
  // already gates verification_history payload emission on dev_mode,
  // so this prop is mostly a defense-in-depth flag for explicit hiding
  // in user-facing surfaces.
  devMode?: boolean;
}

export function ReportRenderer({
  schema,
  loading = false,
  sectionTitles = [],
  theme,
  related,
  reportId,
  devMode = false,
}: ReportRendererProps) {
  const { t } = useTranslation();
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
  const runSummary = schema.run_summary ?? null;
  const verificationHistory =
    devMode && schema.verification_history ? schema.verification_history : null;
  const tocSections = schema.sections.map((s) => ({ id: s.id, title: s.title }));
  if (citations.length) {
    tocSections.push({ id: SOURCES_SECTION_ID, title: t('report.sources_and_disclosures') });
  }
  if (runSummary) {
    tocSections.push({ id: RUN_SUMMARY_SECTION_ID, title: t('report.run_summary') });
  }
  if (verificationHistory) {
    tocSections.push({
      id: VERIFICATION_HISTORY_SECTION_ID,
      title: t('report.verification_history'),
    });
  }
  const hasRailPanel =
    !!schema.rail &&
    (!!schema.rail.verdict ||
      (schema.rail.quick_stats && schema.rail.quick_stats.length > 0) ||
      !!schema.rail.sparkline ||
      (related && related.length > 0));
  const hasRail = hasRailPanel || citations.length > 0;

  const sectionIds = tocSections.map((t) => t.id);

  return (
    <div data-report-theme={resolvedTheme} className={`report${hasRail ? ' report--3col' : ''}`}>
      {furniture ? (
        <ReportHeader
          left={furniture.header.left}
          right={furniture.header.right}
          printHref={reportId ? `/reports/${reportId}/render` : undefined}
        />
      ) : null}
      <div className="report__body">
        <aside className="report__toc">
          <TableOfContents
            sections={tocSections}
            activeId={activeId}
            onSectionClick={setActiveId}
          />
          {schema.meta_stats ? <MetaStatsCard stats={schema.meta_stats} /> : null}
        </aside>
        <main className="report__main">
          <ReportCover cover={schema.cover} />
          <ScrollTracker sectionIds={sectionIds} onActiveId={setActiveId} />
          {schema.sections.map((s, idx) => (
            <ReportSection
              key={s.id}
              id={s.id}
              title={s.title}
              blocks={s.blocks as any[]}
              sectionIndex={idx}
            />
          ))}
          {citations.length ? <CitationsSection citations={citations} /> : null}
          {runSummary ? <RunSummary summary={runSummary} /> : null}
          {verificationHistory ? (
            <VerificationHistory history={verificationHistory} devMode={devMode} />
          ) : null}
        </main>
        {hasRail ? (
          <aside className="report__rail">
            {hasRailPanel ? <RailPanel rail={schema.rail!} related={related} /> : null}
            <CitationsRail citations={citations} />
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
