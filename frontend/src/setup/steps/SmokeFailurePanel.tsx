import type { SmokeFailure } from "../../api/runner_specs";

interface Props {
  failure: SmokeFailure;
  onRetry?: () => void;
  onOpenConnectorSettings?: () => void;
}

const COPY: Record<SmokeFailure["status"], { title: string; help: string }> = {
  auth: {
    title: "Authentication failed",
    help: "The connector's API key was rejected. Update the key in connector settings and retry.",
  },
  bad_params: {
    title: "Endpoint rejected the parameters",
    help: "The picked endpoint returned 400 with the canonical test args. Try a different endpoint or adjust the binding.",
  },
  schema_miss: {
    title: "Response shape didn't match",
    help: "The endpoint succeeded but the result didn't expose the required fields. Try a different endpoint.",
  },
  empty: {
    title: "Endpoint returned no data",
    help: "The call succeeded but returned an empty result. Confirm the endpoint actually has data for the canonical test args.",
  },
  transient: {
    title: "Endpoint is unreachable",
    help: "Network or upstream error after 3 attempts. Try again later.",
  },
  success: {
    title: "Smoke succeeded",
    help: "(internal: success rendered in failure panel)",
  },
};

export function SmokeFailurePanel({
  failure,
  onRetry,
  onOpenConnectorSettings,
}: Props) {
  const copy = COPY[failure.status];
  return (
    <div className="smoke-failure-panel" data-status={failure.status} role="alert">
      <h4>{copy.title}</h4>
      <p>{copy.help}</p>
      {failure.error_message ? (
        <pre className="smoke-failure-error">{failure.error_message}</pre>
      ) : null}
      <div className="smoke-failure-actions">
        {failure.status === "auth" && onOpenConnectorSettings ? (
          <button type="button" onClick={onOpenConnectorSettings}>
            Open connector settings
          </button>
        ) : null}
        {onRetry ? (
          <button type="button" onClick={onRetry}>
            Retry smoke
          </button>
        ) : null}
      </div>
    </div>
  );
}
