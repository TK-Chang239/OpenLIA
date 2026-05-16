import type { Rail, Sparkline as SparklineData } from '../../api/reports';

const W = 280;
const H = 60;

function formatY(v: number): string {
  if (Math.abs(v) >= 1000) return v.toFixed(0);
  if (Math.abs(v) >= 100) return v.toFixed(1);
  return v.toFixed(2);
}

function Sparkline({ data, gradientId }: { data: SparklineData; gradientId: string }) {
  const { points, label } = data;
  if (points.length < 2) return null;
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const xRange = xMax - xMin || 1;
  const yRange = yMax - yMin || 1;

  const coords = points.map((p) => {
    const x = ((p.x - xMin) / xRange) * W;
    const y = H - ((p.y - yMin) / yRange) * (H - 6) - 3;
    return [x, y] as const;
  });
  const linePath = coords
    .map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`)
    .join(' ');
  const lastIdx = coords.length - 1;
  const last = coords[lastIdx]!;
  const fillPath = `${linePath} L${W},${H} L0,${H} Z`;

  return (
    <div className="report-rail__sparkline">
      <div className="report-rail__sparkline-label">{label}</div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--report-accent)" stopOpacity={0.35} />
            <stop offset="100%" stopColor="var(--report-accent)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <path d={fillPath} fill={`url(#${gradientId})`} />
        <path
          d={linePath}
          fill="none"
          stroke="var(--report-text-primary)"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
        <circle
          cx={last[0]}
          cy={last[1]}
          r={3}
          fill="var(--report-accent)"
          stroke="var(--report-text-primary)"
          strokeWidth={1.2}
        />
      </svg>
      <div className="report-rail__sparkline-foot">
        <span>LO {formatY(yMin)}</span>
        <span>HI {formatY(yMax)}</span>
      </div>
    </div>
  );
}

export interface RailPanelProps {
  rail: Rail;
  related?: { title: string; ticker?: string | null; href: string }[];
}

export function RailPanel({ rail, related }: RailPanelProps) {
  const verdict = rail.verdict;
  return (
    <div className="report-rail">
      {verdict ? (
        <section className="report-rail__card report-rail__verdict">
          <div className="report-rail__card-label">Lia's Call</div>
          <div className="report-rail__verdict-row">
            <span className="report-rail__rating">{verdict.rating}</span>
            {verdict.previous_rating ? (
              <span className="report-rail__previous">prev. {verdict.previous_rating}</span>
            ) : null}
          </div>
          {verdict.target ? (
            <div className="report-rail__target">
              {verdict.target}
              {verdict.upside ? <small> {verdict.upside}</small> : null}
            </div>
          ) : null}
          {verdict.as_of ? <div className="report-rail__as-of">{verdict.as_of}</div> : null}
          {rail.sparkline ? <Sparkline data={rail.sparkline} gradientId="railSparkVerdict" /> : null}
        </section>
      ) : null}

      {rail.quick_stats && rail.quick_stats.length > 0 ? (
        <section className="report-rail__card report-rail__stats">
          <div className="report-rail__card-label">Quick Stats</div>
          <dl>
            {rail.quick_stats.map((m) => (
              <div key={m.label} className="report-rail__stat-row">
                <dt>{m.label}</dt>
                <dd data-tone={m.tag?.tone ?? m.delta_direction ?? 'neutral'}>{m.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      {rail.sparkline && !verdict ? (
        <section className="report-rail__card">
          <div className="report-rail__card-label">{rail.sparkline.label}</div>
          <Sparkline data={rail.sparkline} gradientId="railSparkStandalone" />
        </section>
      ) : null}

      {related && related.length > 0 ? (
        <section className="report-rail__card report-rail__related">
          <div className="report-rail__card-label">Related</div>
          <ul>
            {related.map((r) => (
              <li key={r.href}>
                <a href={r.href}>
                  <span>{r.title}</span>
                  {r.ticker ? <span className="report-rail__related-ticker">{r.ticker}</span> : null}
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
