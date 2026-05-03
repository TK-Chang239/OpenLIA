import { useEffect, useState } from "react";
import {
  acceptDisclaimer,
  fetchDisclaimer,
  fetchDisclaimerStatus,
  type DisclaimerPayload,
} from "../api/disclaimer";

export interface DisclaimerGateState {
  loading: boolean;
  needsAcceptance: boolean;
  disclaimer: DisclaimerPayload | null;
  accept: () => Promise<void>;
}

export function useDisclaimerGate(mode: "personal" | "company"): DisclaimerGateState {
  const [loading, setLoading] = useState(true);
  const [needsAcceptance, setNeedsAcceptance] = useState(false);
  const [disclaimer, setDisclaimer] = useState<DisclaimerPayload | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [payload, status] = await Promise.all([
          fetchDisclaimer(),
          fetchDisclaimerStatus(mode),
        ]);
        if (cancelled) return;
        setDisclaimer(payload);
        setNeedsAcceptance(!status.accepted);
      } catch {
        // If the disclaimer endpoint is unavailable, unblock the app.
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mode]);

  const accept = async () => {
    if (!disclaimer) return;
    await acceptDisclaimer(mode, disclaimer.version);
    setNeedsAcceptance(false);
  };

  return { loading, needsAcceptance, disclaimer, accept };
}
