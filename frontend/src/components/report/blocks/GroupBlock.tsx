import type { ReactNode } from 'react';

const CHART_TYPES = new Set([
  'line_chart',
  'bar_chart',
  'area_chart',
  'pie_chart',
  'candlestick_chart',
  'waterfall_chart',
  'scatter_plot',
  'heatmap',
  'treemap',
  'combo_chart',
]);

export type ForcedHeight = 'small' | 'medium' | 'tall' | null;
export type GroupChildRenderer = (child: any, forcedHeight: ForcedHeight) => ReactNode;

export interface GroupBlockProps {
  type: 'group';
  columns: number;
  blocks: any[];
  renderChild: GroupChildRenderer;
}

function rankHeight(h: string | undefined): number {
  switch (h) {
    case 'tall': return 3;
    case 'medium': return 2;
    case 'small': return 1;
    default: return 2;
  }
}

function labelFromRank(rank: number): 'small' | 'medium' | 'tall' {
  if (rank >= 3) return 'tall';
  if (rank <= 1) return 'small';
  return 'medium';
}

function normalizeHeights(blocks: any[]): ForcedHeight[] {
  const isChart = blocks.map((b) => CHART_TYPES.has(b.type));
  const anyChart = isChart.some(Boolean);
  const anyTable = blocks.some((b) => b.type === 'table');
  if (anyChart && !anyTable) {
    const maxRank = Math.max(...blocks.map((b) => rankHeight(b.options?.height)));
    const label = labelFromRank(maxRank);
    return blocks.map((_, i) => (isChart[i] ? label : null));
  }
  if (anyChart && anyTable) {
    return blocks.map((_, i) => (isChart[i] ? 'medium' : null));
  }
  return blocks.map(() => null);
}

export function GroupBlock({ columns, blocks, renderChild }: GroupBlockProps) {
  const forced = normalizeHeights(blocks);
  return (
    <div
      className="group-block"
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
        gap: 'var(--report-group-gap, 20px)',
        alignItems: 'flex-start',
      }}
    >
      {blocks.map((b, i) => (
        <div key={i}>{renderChild(b, forced[i])}</div>
      ))}
    </div>
  );
}
