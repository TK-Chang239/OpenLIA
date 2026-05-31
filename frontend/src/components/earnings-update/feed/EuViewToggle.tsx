import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Calendar, List } from "lucide-react";
import { useTranslation } from "react-i18next";

export type EuView = "stream" | "calendar";

interface Props {
  view: EuView;
  onChange: (next: EuView) => void;
}

const VIEW_IDS: readonly EuView[] = ["stream", "calendar"];

export function EuViewToggle({ view, onChange }: Props) {
  const { t } = useTranslation();
  const btnRefs = useRef<Map<EuView, HTMLButtonElement>>(new Map());
  const [pillStyle, setPillStyle] = useState<{ left: number; width: number } | null>(
    null,
  );

  useLayoutEffect(() => {
    const btn = btnRefs.current.get(view);
    if (btn) setPillStyle({ left: btn.offsetLeft, width: btn.offsetWidth });
  }, [view]);

  useEffect(() => {
    function onResize() {
      const btn = btnRefs.current.get(view);
      if (btn) setPillStyle({ left: btn.offsetLeft, width: btn.offsetWidth });
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [view]);

  return (
    <div
      role="tablist"
      aria-label={t("earnings.view.aria")}
      className="inline-flex p-[3px] border border-[--color-border-subtle] rounded-lg bg-[--color-bg-elevated] relative"
    >
      {pillStyle ? (
        <span
          aria-hidden
          className="absolute top-[3px] bottom-[3px] bg-[--color-text-primary] rounded-[5px] z-[1] pointer-events-none transition-[left,width] duration-[320ms] ease-[cubic-bezier(0.32,0.72,0,1)]"
          style={{ left: pillStyle.left, width: pillStyle.width }}
        />
      ) : null}
      {VIEW_IDS.map((id) => {
        const isOn = id === view;
        const Icon = id === "stream" ? List : Calendar;
        return (
          <button
            key={id}
            ref={(el) => {
              if (el) btnRefs.current.set(id, el);
            }}
            type="button"
            role="tab"
            aria-selected={isOn}
            data-view={id}
            onClick={() => onChange(id)}
            className={`relative z-[2] inline-flex items-center gap-1.5 bg-transparent border-0 px-3 py-1.5 text-[12.5px] cursor-pointer rounded-[5px] transition-colors duration-[220ms] ${
              isOn
                ? "text-[--color-bg-base]"
                : "text-[--color-text-secondary] hover:text-[--color-text-primary]"
            }`}
          >
            <Icon size={13} />
            {t(`earnings.view.${id}`)}
          </button>
        );
      })}
    </div>
  );
}
