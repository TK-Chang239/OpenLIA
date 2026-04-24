import { useCallback, useEffect, useState } from "react";
import {
  getConfig,
  getDashboard,
  getSpikes,
  runSnapshot,
  updateConfig,
  type RsConfig,
  type RsDashboard,
  type RsSnapshot,
  type RsSpike,
} from "../../api/retail-sentiment";

type Tab = "overview" | "per_stock" | "spikes";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "per_stock", label: "Per Stock" },
  { id: "spikes", label: "Spikes" },
];

function formatNumber(value: number | null, digits = 2): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(digits);
}

function sentimentTone(score: number): string {
  if (score > 0.2) return "#2f855a";
  if (score < -0.2) return "#c53030";
  return "#4a5568";
}

function MetricCard(props: {
  label: string;
  value: number | null;
  digits?: number;
  muted?: boolean;
}): JSX.Element {
  return (
    <div
      style={{
        padding: "12px 16px",
        borderRadius: 8,
        border: "1px solid #e2e8f0",
        background: props.muted ? "#f7fafc" : "white",
      }}
    >
      <div style={{ fontSize: 11, textTransform: "uppercase", color: "#718096" }}>
        {props.label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 600, color: "#1a202c" }}>
        {formatNumber(props.value, props.digits ?? 2)}
      </div>
    </div>
  );
}

function SnapshotCard({ snap }: { snap: RsSnapshot }): JSX.Element {
  return (
    <div
      style={{
        padding: 16,
        borderRadius: 10,
        border: "1px solid #e2e8f0",
        background: "white",
        marginBottom: 12,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: 18, fontWeight: 700 }}>{snap.ticker}</div>
        <div
          style={{
            fontSize: 14,
            fontWeight: 600,
            color: sentimentTone(snap.sentiment_score),
          }}
        >
          sentiment {formatNumber(snap.sentiment_score)}
        </div>
      </div>
      <div
        style={{
          marginTop: 12,
          display: "grid",
          gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
          gap: 8,
        }}
      >
        <MetricCard label="Buzz Vol" value={snap.buzz_volume} digits={0} />
        <MetricCard label="Momentum" value={snap.sentiment_momentum} />
        <MetricCard label="Bull/Bear" value={snap.bull_bear_ratio} />
        <MetricCard label="Velocity/hr" value={snap.social_velocity} />
        <MetricCard label="Divergence" value={snap.buzz_sentiment_divergence} />
        <MetricCard label="X-Source" value={snap.cross_source_agreement} />
        <MetricCard
          label="P/C Ratio"
          value={snap.put_call_ratio}
          muted={snap.put_call_ratio === null}
        />
        <MetricCard
          label="Short Press"
          value={snap.short_interest_pressure}
          muted={snap.short_interest_pressure === null}
        />
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: "#718096" }}>
        captured {new Date(snap.captured_at).toLocaleString()}
      </div>
    </div>
  );
}

export default function RetailSentiment(): JSX.Element {
  const [tab, setTab] = useState<Tab>("overview");
  const [dashboard, setDashboard] = useState<RsDashboard | null>(null);
  const [spikes, setSpikes] = useState<RsSpike[]>([]);
  const [config, setConfig] = useState<RsConfig | null>(null);
  const [runTicker, setRunTicker] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [d, s, c] = await Promise.all([
        getDashboard(),
        getSpikes(),
        getConfig(),
      ]);
      setDashboard(d);
      setSpikes(s.spikes);
      setConfig(c);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onRun = useCallback(async () => {
    if (!runTicker.trim()) return;
    setBusy(true);
    try {
      await runSnapshot(
        runTicker
          .split(",")
          .map((t) => t.trim().toUpperCase())
          .filter(Boolean),
      );
      setRunTicker("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [runTicker, refresh]);

  const onTabChange = useCallback(
    async (next: Tab) => {
      setTab(next);
      if (config && config.active_tab !== next) {
        try {
          const updated = await updateConfig({ active_tab: next });
          setConfig(updated);
        } catch {
          // Non-fatal: tab persistence is best-effort.
        }
      }
    },
    [config],
  );

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Retail Sentiment</h1>
      <p style={{ color: "#4a5568", marginBottom: 16 }}>
        Monitor social + news sentiment, buzz volume, and cross-source agreement for tickers.
      </p>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => void onTabChange(t.id)}
            style={{
              padding: "8px 16px",
              borderRadius: 6,
              border: "1px solid #e2e8f0",
              background: tab === t.id ? "#2d3748" : "white",
              color: tab === t.id ? "white" : "#2d3748",
              cursor: "pointer",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div
        style={{
          marginBottom: 16,
          padding: 12,
          borderRadius: 8,
          border: "1px solid #e2e8f0",
          background: "#f7fafc",
          display: "flex",
          gap: 8,
          alignItems: "center",
        }}
      >
        <input
          value={runTicker}
          onChange={(e) => setRunTicker(e.target.value)}
          placeholder="AAPL,MSFT"
          style={{
            flex: 1,
            padding: "8px 12px",
            borderRadius: 6,
            border: "1px solid #cbd5e0",
          }}
        />
        <button
          type="button"
          onClick={() => void onRun()}
          disabled={busy || !runTicker.trim()}
          style={{
            padding: "8px 16px",
            borderRadius: 6,
            background: "#2b6cb0",
            color: "white",
            border: "none",
            cursor: busy ? "wait" : "pointer",
          }}
        >
          {busy ? "Running…" : "Run snapshot"}
        </button>
        <button
          type="button"
          onClick={() => void refresh()}
          style={{
            padding: "8px 16px",
            borderRadius: 6,
            background: "white",
            border: "1px solid #cbd5e0",
            cursor: "pointer",
          }}
        >
          Refresh
        </button>
      </div>

      {error ? (
        <div
          style={{
            padding: 12,
            borderRadius: 6,
            background: "#fed7d7",
            color: "#742a2a",
            marginBottom: 16,
          }}
        >
          {error}
        </div>
      ) : null}

      {tab === "overview" ? (
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 12 }}>
            Tickers tracked: {dashboard?.tickers.length ?? 0}
          </h2>
          {(dashboard?.snapshots ?? []).length === 0 ? (
            <div style={{ color: "#718096" }}>
              No snapshots yet. Trigger one via the input above.
            </div>
          ) : (
            (dashboard?.snapshots ?? []).map((s) => (
              <SnapshotCard key={s.ticker} snap={s} />
            ))
          )}
        </div>
      ) : null}

      {tab === "per_stock" ? (
        <div>
          {(dashboard?.snapshots ?? []).map((s) => (
            <SnapshotCard key={s.ticker} snap={s} />
          ))}
        </div>
      ) : null}

      {tab === "spikes" ? (
        <div>
          {spikes.length === 0 ? (
            <div style={{ color: "#718096" }}>No spikes detected in the last 7 days.</div>
          ) : (
            spikes.map((sp) => (
              <div
                key={`${sp.ticker}-${sp.detected_at}`}
                style={{
                  padding: 12,
                  borderRadius: 8,
                  border: "1px solid #feb2b2",
                  background: "#fff5f5",
                  marginBottom: 8,
                }}
              >
                <div style={{ fontWeight: 600 }}>{sp.ticker}</div>
                <div style={{ fontSize: 13, color: "#742a2a" }}>
                  buzz={formatNumber(sp.buzz, 0)} · z={formatNumber(sp.z_score)} · baseline{" "}
                  μ={formatNumber(sp.baseline_mean, 1)} σ={formatNumber(sp.baseline_stddev, 1)}
                </div>
              </div>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
