import { useTranslation } from "react-i18next";

export function ChartEmpty(): JSX.Element {
  const { t } = useTranslation();
  return <div className="report-chart__empty">{t("report.no_data")}</div>;
}
