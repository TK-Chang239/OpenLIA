// Market index strip shown on Home (fetchMarketIndices -> /api/markets/indices).

import { register, json } from "../registry";

register([
  {
    method: "GET",
    pattern: "/api/markets/indices",
    handler: () =>
      json({
        indices: [
          { symbol: "GSPC", label: "S&P 500", value: 6218.4, change_pct: 0.42 },
          { symbol: "IXIC", label: "Nasdaq", value: 20431.9, change_pct: 0.71 },
          { symbol: "DJI", label: "Dow", value: 44192.1, change_pct: -0.12 },
          { symbol: "TNX", label: "US 10Y", value: 4.18, change_pct: -0.9 },
          { symbol: "VIX", label: "VIX", value: 14.6, change_pct: -3.4 },
          { symbol: "BTC", label: "BTC", value: 114820, change_pct: 1.8 },
        ],
      }),
  },
]);
