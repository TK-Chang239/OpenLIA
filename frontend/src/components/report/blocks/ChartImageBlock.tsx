/**
 * ChartImageBlock — renders a v2.2 `chart` block (svg_inline or png_base64).
 *
 * v2.2 helpers produce charts as raster (`png_base64`) or inline-SVG
 * (`svg_inline`) payloads instead of structured chart-data dicts, so this
 * block can't reuse the v1 LineChart / BarChart components that work
 * against structured data. It renders the payload as an image / inline
 * SVG inside a figure, matching the visual chrome of the structured
 * chart blocks (border, caption, max-width).
 */
import { useMemo, type JSX } from "react";

export interface ChartImageBlockProps {
  type: "chart_image";
  format: "svg_inline" | "png_base64";
  payload: string;
  caption?: string;
}

export function ChartImageBlock({
  format,
  payload,
  caption,
}: ChartImageBlockProps): JSX.Element {
  // Inline SVG is rendered via dangerouslySetInnerHTML inside a wrapper that
  // strips it from React's tree. The payload comes from our own backend
  // helpers; we don't accept user-authored SVG here. PNG is just an <img>.
  const html = useMemo(
    () => (format === "svg_inline" ? { __html: payload } : null),
    [format, payload],
  );

  return (
    <figure
      className="my-3 rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] p-3"
      data-block-type="chart_image"
    >
      <div className="w-full overflow-auto">
        {format === "svg_inline" && html ? (
          <div dangerouslySetInnerHTML={html} className="w-full" />
        ) : (
          <img
            src={`data:image/png;base64,${payload}`}
            alt={caption ?? "Chart"}
            className="block w-full"
          />
        )}
      </div>
      {caption ? (
        <figcaption className="mt-2 text-[11.5px] leading-[1.5] text-[--color-text-tertiary]">
          {caption}
        </figcaption>
      ) : null}
    </figure>
  );
}
