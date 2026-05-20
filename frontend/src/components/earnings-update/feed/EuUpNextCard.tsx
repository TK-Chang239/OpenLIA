import { useTranslation } from "react-i18next";

import type { DemoUpNext } from "../../../lib/earnings-update/demo-data";

interface Props {
  item: DemoUpNext;
}

export function EuUpNextCard({ item }: Props) {
  const { t } = useTranslation();
  return (
    <article className="flex flex-col gap-2 px-4 py-4 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[10px] hover:border-[--color-border-strong] transition-colors duration-[--duration-normal]">
      <span className="font-mono text-[9px] tracking-[0.14em] uppercase text-[--color-text-tertiary]">
        {item.timing}
      </span>
      <div className="flex items-baseline gap-2.5">
        <span className="font-mono text-[15px] font-semibold tracking-wide text-[--color-text-primary]">
          {item.ticker}
        </span>
        <span className="font-mono text-[10px] tracking-[0.08em] text-[--color-text-tertiary]">
          {item.whenET}
        </span>
      </div>
      <p className="text-[13px] text-[--color-text-secondary] leading-[1.45] m-0">
        {item.description}
      </p>
      <span className="font-mono text-[10.5px] tracking-[0.04em] text-[--color-text-tertiary] mt-0.5">
        {t("earnings.feed.up_next_est_eps")}{" "}
        <strong className="text-[--color-text-secondary] font-semibold">
          {item.estEps}
        </strong>{" "}
        · {t("earnings.feed.up_next_rev")}{" "}
        <strong className="text-[--color-text-secondary] font-semibold">
          {item.estRev}
        </strong>
      </span>
    </article>
  );
}
