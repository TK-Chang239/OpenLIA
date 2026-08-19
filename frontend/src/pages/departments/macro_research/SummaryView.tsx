import { useEffect, useRef, useState } from "react";

import { getDashboard, runAssessment } from "../../../api/macro_research";
import { CitationTableContext } from "../../../lib/citationLinks";
import type { SummaryData } from "../../../lib/macro_research/dalio_copy/types";
import {
  Cascade,
  ConsolidatedWatchlist,
  DepMap,
  FrameworkGrid,
  RegimeBar,
  SummaryHero,
} from "../../../components/macro_research/_shared/summary-widgets";
import {
  DashEmpty,
  DashLoading,
  SectionLabel,
  SectionSub,
  SrcFoot,
} from "../../../components/macro_research/_shared/widgets";

const POLL_INTERVAL_MS = 6000;
const POLL_MAX_ATTEMPTS = 70; // ~7 min; a real macro run takes a few minutes

export default function SummaryView(): JSX.Element {
  const [data, setData] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [, setGeneratedAt] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const load = () => {
    setLoading(true);
    getDashboard<SummaryData>("summary")
      .then((r) => {
        setData(r.payload);
        setGeneratedAt(r.generated_at);
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    return stopPolling;
  }, []);

  const startPolling = () => {
    stopPolling();
    let attempts = 0;
    pollRef.current = setInterval(() => {
      attempts += 1;
      getDashboard<SummaryData>("summary")
        .then((r) => {
          if (r.payload) {
            stopPolling();
            setData(r.payload);
            setGeneratedAt(r.generated_at);
            setGenerating(false);
            setNote(null);
          } else if (attempts >= POLL_MAX_ATTEMPTS) {
            stopPolling();
            setGenerating(false);
            setNote("Still generating. Reload in a moment to see the result.");
          }
        })
        .catch(() => undefined);
    }, POLL_INTERVAL_MS);
  };

  const onGenerate = () => {
    setNote(
      "Generating a live reading from current data — this can take a few minutes. Keep this tab open.",
    );
    setGenerating(true);
    runAssessment("summary")
      .then((r) => {
        if (r.status === "queued") {
          startPolling();
        } else if (r.status === "already_running") {
          // A run is already in flight (e.g. another tab) — watch for it.
          setNote("A reading is already being generated — watching for the result.");
          startPolling();
        } else {
          setGenerating(false);
          setNote("Generation could not start (background scheduler unavailable).");
        }
      })
      .catch(() => {
        setGenerating(false);
        setNote("Could not start generation. Please try again.");
      });
  };

  if (loading) return <DashLoading />;
  if (!data) return <DashEmpty onGenerate={onGenerate} generating={generating} note={note} />;

  return (
    <CitationTableContext.Provider value={data.citations ?? null}>
    <article>
      <SummaryHero hero={data.hero} liaTake={data.liaTake} />

      <SectionLabel first count={data.regimeBar.subLabel}>
        {data.regimeBar.label}
      </SectionLabel>
      <RegimeBar segments={data.regimeBar.segments} testid="summary-regime-bar" />

      <SectionLabel count={data.frameworkStatus.subLabel}>
        {data.frameworkStatus.label}
      </SectionLabel>
      <FrameworkGrid cards={data.frameworkStatus.cards} testid="summary-framework-grid" />

      <SectionLabel count={data.depMap.subLabel}>{data.depMap.label}</SectionLabel>
      <SectionSub>{data.depMap.sub}</SectionSub>
      <DepMap nodes={data.depMap.nodes} edges={data.depMap.edges} testid="summary-dep-map" />

      <SectionLabel count={data.cascade.subLabel}>{data.cascade.label}</SectionLabel>
      <SectionSub>{data.cascade.sub}</SectionSub>
      <Cascade row1={data.cascade.row1} row2={data.cascade.row2} testid="summary-cascade" />

      <SectionLabel count={data.watchlist.subLabel}>{data.watchlist.label}</SectionLabel>
      <ConsolidatedWatchlist triggers={data.watchlist.triggers} testid="summary-watchlist" />

      <SrcFoot>
        <strong>Sources · </strong>
        {data.sources}
      </SrcFoot>
    </article>
    </CitationTableContext.Provider>
  );
}
