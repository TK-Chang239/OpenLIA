import { Navigate, useParams } from "react-router-dom";
import type { JSX } from "react";

import { PortfolioShell } from "../portfolio/PortfolioShell";
import type { Market } from "../portfolio/marketTypes";

const VALID_MARKETS: readonly Market[] = ["us", "tw"];

export default function PortfolioPage(): JSX.Element {
  const { market } = useParams<{ market: string }>();
  const normalized = (market ?? "").toLowerCase();
  if (!VALID_MARKETS.includes(normalized as Market)) {
    return <Navigate to="/portfolio/us" replace />;
  }
  return <PortfolioShell market={normalized as Market} />;
}
