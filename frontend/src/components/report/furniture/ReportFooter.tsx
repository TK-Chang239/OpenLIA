export interface ReportFooterProps {
  left: string;
  center: string;
  right: string;
  disclaimer: string;
}

export function ReportFooter({ left, center, right, disclaimer }: ReportFooterProps) {
  return (
    <footer className="report-furniture__footer">
      <div className="report-furniture__footer-row">
        <span>{left}</span>
        <span>{center}</span>
        <span>{right}</span>
      </div>
      <p className="report-furniture__disclaimer">{disclaimer}</p>
    </footer>
  );
}
