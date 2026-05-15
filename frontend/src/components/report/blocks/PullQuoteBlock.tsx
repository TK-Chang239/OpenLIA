import type { JSX } from "react";
import { PullQuote } from "../../chat/PullQuote";

export interface PullQuoteBlockData {
  type: "pull_quote";
  text: string;
  attribution?: string | null;
  source?: string | null;
  timestamp?: string | null;
}

/** Report adapter for the shared `PullQuote` chat primitive. Same visual
 *  treatment (left border accent + tinted bg + mono citation) so chat and
 *  report renders stay in lockstep. */
export function PullQuoteBlock(props: PullQuoteBlockData): JSX.Element {
  return (
    <PullQuote
      text={props.text}
      attribution={props.attribution ?? null}
      source={props.source ?? null}
      timestamp={props.timestamp ?? null}
    />
  );
}
