export interface ReportHeaderProps { left: string; right: string; }

export function ReportHeader({ left, right }: ReportHeaderProps) {
  return (
    <div className="report-furniture__header">
      <span className="report-furniture__header-left">{left}</span>
      <span className="report-furniture__header-right">{right}</span>
    </div>
  );
}
