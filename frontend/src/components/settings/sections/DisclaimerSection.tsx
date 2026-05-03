import { type FC, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  fetchDisclaimer,
  fetchDisclaimerStatus,
  type DisclaimerPayload,
  type DisclaimerStatus,
} from "../../../api/disclaimer";

interface Props {
  mode: "personal" | "company";
}

export const DisclaimerSection: FC<Props> = ({ mode }) => {
  const [payload, setPayload] = useState<DisclaimerPayload | null>(null);
  const [status, setStatus] = useState<DisclaimerStatus | null>(null);
  useEffect(() => {
    Promise.all([fetchDisclaimer(), fetchDisclaimerStatus(mode)]).then(([p, s]) => {
      setPayload(p);
      setStatus(s);
    });
  }, [mode]);
  if (!payload || !status) return null;
  const stale =
    status.accepted_version && status.accepted_version !== status.current_version;
  return (
    <section>
      <h2 className="text-base font-semibold">Compliance disclaimer</h2>
      <p className="mt-1 text-xs text-slate-500">
        Version {status.current_version} . Accepted: {status.accepted ? "yes" : "no"}
        {stale ? ` (you accepted ${status.accepted_version}; please re-accept)` : ""}
      </p>
      <div className="prose prose-sm mt-3 max-h-96 overflow-y-auto rounded border border-slate-200 p-3">
        <ReactMarkdown>{payload.text}</ReactMarkdown>
      </div>
    </section>
  );
};
