import Skeleton from 'react-loading-skeleton';
import 'react-loading-skeleton/dist/skeleton.css';

export interface ReportSkeletonProps {
  sectionTitles?: string[];
}

export function ReportSkeleton({ sectionTitles = [] }: ReportSkeletonProps) {
  return (
    <div className="report-skeleton">
      <div className="report-skeleton__cover">
        <Skeleton width="60%" height={28} />
        <Skeleton width="40%" height={18} style={{ marginTop: 8 }} />
        <Skeleton height={90} style={{ marginTop: 24 }} />
      </div>
      {sectionTitles.map((title, i) => (
        <div key={`${i}-${title}`} className="report-skeleton__section">
          <h2 className="report-skeleton__heading">{title}</h2>
          <Skeleton count={3} />
          <Skeleton height={260} style={{ marginTop: 16 }} />
          <Skeleton count={4} style={{ marginTop: 16 }} />
        </div>
      ))}
    </div>
  );
}
