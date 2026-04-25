import type { PanelResult } from "../../api/panic-thermometer";

interface Props {
  result: PanelResult | undefined;
}

export function InflationDashboard({ result }: Props): JSX.Element {
  const tipPrice = Number(result?.resolved_values?.tip_price_latest ?? 0);
  const tipPrev = Number(result?.resolved_values?.tip_prev_close ?? 0);
  const michigan = result?.resolved_values?.michigan_5y;
  const michiganPrev = result?.resolved_values?.michigan_prev;

  return (
    <div data-testid="inflation-dashboard">
      <h4>Inflation Expectations</h4>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <tbody>
          <tr>
            <td style={{ padding: "0.25rem 0" }}>TIP price</td>
            <td style={{ textAlign: "right" }}>${tipPrice.toFixed(2)}</td>
            <td style={{ textAlign: "right" }}>
              prev ${tipPrev.toFixed(2)}
            </td>
          </tr>
          <tr>
            <td style={{ padding: "0.25rem 0" }}>Michigan 5Y survey</td>
            <td style={{ textAlign: "right" }}>
              {michigan == null ? "n/a" : `${Number(michigan).toFixed(2)}%`}
            </td>
            <td style={{ textAlign: "right" }}>
              prev{" "}
              {michiganPrev == null
                ? "n/a"
                : `${Number(michiganPrev).toFixed(2)}%`}
            </td>
          </tr>
        </tbody>
      </table>
      <p style={{ color: "var(--color-text-secondary)", fontSize: "0.85rem" }}>
        Dual-axis: TIP price (left) and Michigan 5Y inflation expectations
        (right).
      </p>
    </div>
  );
}
