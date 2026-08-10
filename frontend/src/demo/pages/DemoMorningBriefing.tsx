import { useCallback, useState } from "react";
import { MockupEmbed } from "../embed/MockupEmbed";
import { OverlayEmbed } from "../embed/OverlayEmbed";

// Morning Briefings — adopted mockup (editorial hero + stat band + Today section
// + live-generating card). The header's Schedules and Library buttons open the
// corresponding sub-screen mockups in an overlay.
export default function DemoMorningBriefing(): JSX.Element {
  const [overlay, setOverlay] = useState<{ url: string; label: string } | null>(null);

  const wire = useCallback((root: ShadowRoot) => {
    const buttons = Array.from(root.querySelectorAll<HTMLElement>(".top-btn"));
    const byText = (re: RegExp) => buttons.find((el) => re.test(el.textContent ?? ""));
    const sched = byText(/schedules/i);
    const lib = byText(/library/i);
    const openSched = () =>
      setOverlay({ url: "/demo-mockups/morning-briefing-schedules.html", label: "Schedules" });
    const openLib = () =>
      setOverlay({ url: "/demo-mockups/morning-briefing-library.html", label: "Library" });
    sched?.addEventListener("click", openSched);
    lib?.addEventListener("click", openLib);
    return () => {
      sched?.removeEventListener("click", openSched);
      lib?.removeEventListener("click", openLib);
    };
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
