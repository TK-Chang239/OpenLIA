import { useState } from "react";
import { useTranslation } from "react-i18next";

interface Props {
  newReportId: string;
}

export function RevisionInProgressChip({ newReportId }: Props) {
  const { t } = useTranslation();
  const [cancelled, setCancelled] = useState(false);

  async function handleCancel() {
    if (!confirm(t("chat.cancel_revision_confirm"))) return;
    await fetch(`/reports/${newReportId}`, { method: "DELETE" });
    setCancelled(true);
  }

  return (
    <div className={`chip chip--revision ${cancelled ? "chip--cancelled" : ""}`}>
      <span className="spinner" aria-hidden="true" />
      <span>{cancelled ? t("chat.revision_cancelled") : t("chat.revision_in_progress")}</span>
      {!cancelled && (
        <button onClick={handleCancel}>{t("chat.cancel_revision")}</button>
      )}
    </div>
  );
}
