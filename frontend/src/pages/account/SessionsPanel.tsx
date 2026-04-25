import { Loader2 } from "lucide-react";
import { useState } from "react";
import { logoutAll } from "../../api/auth";
import { ApiError } from "../../api/client";
import { mapTransportError } from "../../api/errors";
import { Banner, type BannerVariant } from "../../components/primitives/Banner";

export function SessionsPanel() {
  const [submitting, setSubmitting] = useState(false);
  const [banner, setBanner] = useState<
    { message: string; variant: BannerVariant } | null
  >(null);

  async function onClick() {
    setSubmitting(true);
    setBanner(null);
    try {
      await logoutAll();
      setBanner({ message: "Other sessions signed out.", variant: "success" });
    } catch (err) {
      if (
        err instanceof TypeError ||
        (err instanceof ApiError && (err.status === 0 || err.status >= 500))
      ) {
        setBanner(mapTransportError(err));
      } else {
        setBanner({
          message: "Unable to sign out other sessions. Please try again.",
          variant: "error",
        });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-md">
      <p className="text-sm text-text-primary mb-4">
        You are signed in on this device.
      </p>
      {banner && <Banner variant={banner.variant} message={banner.message} />}
      <button
        type="button"
        onClick={() => {
          void onClick();
        }}
        disabled={submitting}
        aria-busy={submitting}
        className="h-10 px-4 rounded-md border border-border-subtle bg-bg-elevated text-sm font-medium text-text-primary hover:bg-surface-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label="Loading" />
        ) : null}
        Sign out all other devices
      </button>
    </div>
  );
}
