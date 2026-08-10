import { useCallback, useState } from "react";
import { MockupEmbed } from "../embed/MockupEmbed";
import { OverlayEmbed } from "../embed/OverlayEmbed";

// Morning Briefings — adopted mockup (editorial hero + stat band + Today section
// + live-generating card). Header buttons match the provided version: Schedules
// and Library open their sub-screen mockups; Run now opens the run-now popup
// with the Generate button disabled (nothing generates in the demo).
export default function DemoMorningBriefing(): JSX.Element {
  const [overlay, setOverlay] = useState<{ url: string; label: string } | null>(null);

  const wire = useCallback((root: ShadowRoot) => {
    const cleanups: Array<() => void> = [];
    const on = (el: Element | null, ev: string, fn: EventListener) => {
      if (!el) return;
      el.addEventListener(ev, fn);
      cleanups.push(() => el.removeEventListener(ev, fn));
    };

    const buttons = Array.from(root.querySelectorAll<HTMLElement>(".top-btn"));
    const byText = (re: RegExp) => buttons.find((el) => re.test(el.textContent ?? ""));

    on(byText(/schedules/i) ?? null, "click", () =>
      setOverlay({ url: "/demo-mockups/morning-briefing-schedules.html", label: "Schedules" }),
    );
    on(byText(/library/i) ?? null, "click", () =>
      setOverlay({ url: "/demo-mockups/morning-briefing-library.html", label: "Library" }),
    );

    // Run now — reveal the embedded popup (#runModal), but keep Generate disabled.
    const runModal = root.querySelector<HTMLElement>("#runModal");
    const closeRun = () => runModal?.classList.remove("open");
    on(root.querySelector("#runBtn"), "click", () => runModal?.classList.add("open"));
    on(root.querySelector("#runClose"), "click", closeRun);
    on(root.querySelector("#runCancel"), "click", closeRun);
    on(runModal, "click", (e) => {
      if (e.target === runModal) closeRun();
    });
    const gen = root.querySelector<HTMLButtonElement>("#runGenerate");
    if (gen) {
      gen.disabled = true;
      gen.style.opacity = "0.45";
      gen.style.cursor = "not-allowed";
      gen.title = "Generating is disabled in the demo";
    }

    return () => cleanups.forEach((fn) => fn());
  }, []);

  return (
    <>
      <MockupEmbed url="/demo-mockups/morning-briefing.html" onReady={wire} />
      {overlay && (
        <OverlayEmbed url={overlay.url} label={overlay.label} onClose={() => setOverlay(null)} />
      )}
    </>
  );
}
