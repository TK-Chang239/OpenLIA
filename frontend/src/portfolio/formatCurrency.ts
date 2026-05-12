/** Format a number in the holding's native currency.
 *  USD -> $1,234.56, TWD -> NT$1,234, others -> CCC 1,234.56. */
export function formatCurrency(
  amount: number | null,
  currency: string,
  opts: { signed?: boolean; compact?: boolean } = {},
): string {
  if (amount === null || !Number.isFinite(amount)) return "—";
  const ccy = currency.toUpperCase();
  const abs = Math.abs(amount);
  const fracDigits = ccy === "TWD" || ccy === "JPY" || ccy === "KRW" ? 0 : 2;
  const body = abs.toLocaleString("en-US", {
    minimumFractionDigits: fracDigits,
    maximumFractionDigits: fracDigits,
  });
  const sign = opts.signed ? (amount >= 0 ? "+" : "-") : amount < 0 ? "-" : "";
  if (ccy === "USD") return `${sign}$${body}`;
  if (ccy === "TWD") return `${sign}NT$${body}`;
  return `${sign}${ccy} ${body}`;
}
