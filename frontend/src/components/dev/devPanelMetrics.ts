import type { DevEvent } from "../../api/devEvents";

export interface CostMetrics {
  reportCount: number;
  searchCount: number;
  searchesPerReport: number;
  rescueRate: number;
  doubleBillEstimate: number;
}

interface ReportBucket {
  searchSeqs: Set<number>;
  hasRescue: boolean;
  hasNativeInvoked: boolean;
  hasConfiguredToolCall: boolean;
}

function getReportId(event: DevEvent): string | null {
  const id = event.payload["report_id"];
  return typeof id === "string" && id.length > 0 ? id : null;
}

function getToolName(event: DevEvent): string | null {
  const tool = event.payload["tool"];
  if (typeof tool === "string") return tool;
  const name = event.payload["tool_name"];
  return typeof name === "string" ? name : null;
}

function emptyBucket(): ReportBucket {
  return {
    searchSeqs: new Set<number>(),
    hasRescue: false,
    hasNativeInvoked: false,
    hasConfiguredToolCall: false,
  };
}

export function computeCostMetrics(events: DevEvent[]): CostMetrics {
  const buckets = new Map<string, ReportBucket>();

  for (const event of events) {
    const reportId = getReportId(event);
    if (reportId === null) continue;

    let bucket = buckets.get(reportId);
    if (!bucket) {
      bucket = emptyBucket();
      buckets.set(reportId, bucket);
    }

    if (event.category === "report.web_search.invoked") {
      bucket.searchSeqs.add(event.seq);
      bucket.hasNativeInvoked = true;
    } else if (event.category === "web_search.rescue") {
      bucket.searchSeqs.add(event.seq);
      bucket.hasRescue = true;
    } else if (event.category === "report.tool_call") {
      if (getToolName(event) === "web_search") {
        bucket.searchSeqs.add(event.seq);
        bucket.hasConfiguredToolCall = true;
      }
    }
  }

  const reportCount = buckets.size;
  if (reportCount === 0) {
    return {
      reportCount: 0,
      searchCount: 0,
      searchesPerReport: 0,
      rescueRate: 0,
      doubleBillEstimate: 0,
    };
  }

  let searchCount = 0;
  let reportsWithRescue = 0;
  let reportsWithBoth = 0;
  for (const bucket of buckets.values()) {
    searchCount += bucket.searchSeqs.size;
    if (bucket.hasRescue) reportsWithRescue += 1;
    if (bucket.hasNativeInvoked && bucket.hasConfiguredToolCall) {
      reportsWithBoth += 1;
    }
  }

  return {
    reportCount,
    searchCount,
    searchesPerReport: searchCount / reportCount,
    rescueRate: reportsWithRescue / reportCount,
    doubleBillEstimate: reportsWithBoth / reportCount,
  };
}
