import { useMemo } from 'react';
import { ChartEmpty } from "./ChartEmpty";
import { paletteColor, formatTick } from './svgUtils';
import { useChartTooltip, type UseChartTooltipReturn } from './useChartTooltip';

export interface TreemapNode { name: string; value: number; children?: TreemapNode[]; }

export interface TreemapBlockProps {
  type: 'treemap';
  title: string;
  data: TreemapNode[];
}

interface Tile {
  name: string;
  value: number;
  x: number;
  y: number;
  w: number;
  h: number;
  depth: number;
  children?: Tile[];
}

const W = 720;
const H = 320;

/** Squarified-ish layout: split a rect by the largest child's share, alternating
 *  horizontal/vertical depending on which dimension is longer. Good enough for
 *  ~5–20 top-level items, the typical case for a report. */
function layout(nodes: TreemapNode[], x: number, y: number, w: number, h: number, depth: number): Tile[] {
  if (nodes.length === 0) return [];
  const total = nodes.reduce((acc, n) => acc + n.value, 0) || 1;
  const sorted = [...nodes].sort((a, b) => b.value - a.value);
  const tiles: Tile[] = [];
  let cx = x;
  let cy = y;
  let remW = w;
  let remH = h;
  const horizontal = w >= h;
  let remaining = total;
  for (const n of sorted) {
    const frac = n.value / remaining;
    const tw = horizontal ? remW * frac : remW;
    const th = horizontal ? remH : remH * frac;
    const tile: Tile = {
      name: n.name,
      value: n.value,
      x: cx,
      y: cy,
      w: tw,
      h: th,
      depth,
    };
    if (n.children && n.children.length > 0) {
      tile.children = layout(n.children, cx + 4, cy + 18, tw - 8, th - 22, depth + 1);
    }
    tiles.push(tile);
    if (horizontal) {
      cx += tw;
      remW -= tw;
    } else {
      cy += th;
      remH -= th;
    }
    remaining -= n.value;
  }
  return tiles;
}

export function TreemapBlock({ title, data }: TreemapBlockProps) {
  const tiles = useMemo(() => layout(data, 0, 0, W, H, 0), [data]);
  const { figureRef, tooltipNode, hover } = useChartTooltip();

  if (tiles.length === 0) {
    return (
      <figure className="report-chart">
        <figcaption className="report-chart__title">{title}</figcaption>
        <ChartEmpty />
      </figure>
    );
  }

  return (
    <figure className="report-chart" ref={figureRef}>
      <figcaption className="report-chart__title">{title}</figcaption>
      <svg
        className="report-line-chart"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={title}
      >
        {tiles.map((t, i) => (
          <Group key={`${t.name}-${i}`} tile={t} idx={i} hover={hover} />
        ))}
      </svg>
      {tooltipNode}
    </figure>
  );
}

function Group({ tile, idx, hover }: { tile: Tile; idx: number; hover: UseChartTooltipReturn['hover'] }) {
  const fill = paletteColor(idx + tile.depth * 2);
  return (
    <g>
      <rect
        className="hover-target"
        x={tile.x}
        y={tile.y}
        width={tile.w}
        height={tile.h}
        style={{
          fill,
          fillOpacity: 0.18 + tile.depth * 0.05,
          stroke: 'var(--report-border)',
          strokeWidth: 1,
        }}
        {...hover({
          label: tile.name,
          rows: [{ swatch: fill, name: 'Value', value: formatTick(tile.value) }],
        })}
      />
      {tile.w > 60 && tile.h > 24 ? (
        <>
          <text
            x={tile.x + 8}
            y={tile.y + 16}
            style={{ fill: 'var(--report-text-primary)', fontFamily: 'var(--report-font-display)', fontSize: 12, fontWeight: 600 }}
          >
            {tile.name}
          </text>
          {tile.h > 36 ? (
            <text
              x={tile.x + 8}
              y={tile.y + 32}
              style={{ fill: 'var(--report-text-secondary)', fontFamily: 'var(--report-font-mono)', fontSize: 10 }}
            >
              {tile.value}
            </text>
          ) : null}
        </>
      ) : null}
      {tile.children?.map((c, ci) => <Group key={`${c.name}-${ci}`} tile={c} idx={idx} hover={hover} />)}
    </g>
  );
}
