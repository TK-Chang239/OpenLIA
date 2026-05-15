import type { JSX } from "react";
import { PullQuote } from "../../chat/PullQuote";
import { CitationRefs } from "../CitationRefs";

export interface PullQuoteBlockData {
  type: "pull_quote";
  text: string;
  attribution?: string | null;
  source?: string | null;
  timestamp?: string | null;
  source_ids?: string[];
}

/** Report adapter for the shared `PullQuote` chat primitive. Same visual
 *  treatment (left border accent + tinted bg + mono citation) so chat and
 *  report renders stay in lockstep. Inline `[N]` citation markers render
 *  alongside the quote when `source_ids` is populated. */
export function PullQuoteBlock(props: PullQuoteBlockData): JSX.Element {
  const hasRefs = !!props.source_ids && props.source_ids.length > 0;
  return (
    <div className="pull-quote-block">
      <PullQuote
        text={props.text}
        attribution={props.attribution ?? null}
        source={props.source ?? null}
        timestamp={props.timestamp ?? null}
      />
      {hasRefs ? <CitationRefs ids={props.source_ids} /> : null}
    </div>
  );
}
