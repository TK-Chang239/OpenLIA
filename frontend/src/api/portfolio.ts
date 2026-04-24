export interface PortfolioHolding {
  ticker: string;
  name: string | null;
}

export async function fetchHoldings(): Promise<PortfolioHolding[]> {
  const res = await fetch("/api/portfolio/holdings", {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`fetchHoldings failed: ${res.status}`);
  return (await res.json()) as PortfolioHolding[];
}
