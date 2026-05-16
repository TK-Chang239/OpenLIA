import { useCallback, useRef, useState, type MouseEvent, type ReactNode, type Ref } from 'react';

export interface TooltipRow {
  swatch?: string;
  name?: string;
  value: string;
}

export interface TooltipPayload {
  label: string;
  rows: TooltipRow[];
  key?: string | number;
}

interface TooltipState {
  x: number;
  y: number;
  payload: TooltipPayload;
}

interface HoverHandlers {
  onMouseEnter: (e: MouseEvent) => void;
  onMouseMove: (e: MouseEvent) => void;
  onMouseLeave: () => void;
}

export interface UseChartTooltipReturn {
  figureRef: Ref<HTMLElement>;
  tooltipNode: ReactNode;
  hover: (payload: TooltipPayload) => HoverHandlers;
  activeKey: string | number | null;
}

export function useChartTooltip(): UseChartTooltipReturn {
  const figureRef = useRef<HTMLElement>(null);
  const [state, setState] = useState<TooltipState | null>(null);

  const positionFrom = (e: MouseEvent): { x: number; y: number } | null => {
    const rect = figureRef.current?.getBoundingClientRect();
    if (!rect) return null;
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  const hover = useCallback(
    (payload: TooltipPayload): HoverHandlers => ({
      onMouseEnter: (e) => {
        const pos = positionFrom(e);
        if (!pos) return;
        setState({ ...pos, payload });
      },
      onMouseMove: (e) => {
        const pos = positionFrom(e);
        if (!pos) return;
        setState((prev) =>
          prev && prev.payload.key === payload.key
            ? { ...pos, payload: prev.payload }
            : { ...pos, payload },
        );
      },
      onMouseLeave: () => setState(null),
    }),
    [],
  );

  const activeKey = state?.payload.key ?? null;

  const tooltipNode = state ? (
    <div
      className="report-chart__tooltip"
      style={{ left: state.x, top: state.y }}
      role="tooltip"
    >
      <div className="report-chart__tooltip-label">{state.payload.label}</div>
      {state.payload.rows.map((r, i) => (
        <div key={i} className="report-chart__tooltip-row">
          {r.swatch ? (
            <span
              className="report-chart__tooltip-swatch"
              style={{ background: r.swatch }}
            />
          ) : null}
          {r.name ? (
            <span className="report-chart__tooltip-name">{r.name}</span>
          ) : null}
          <span className="report-chart__tooltip-value">{r.value}</span>
        </div>
      ))}
    </div>
  ) : null;

  return { figureRef, tooltipNode, hover, activeKey };
}
