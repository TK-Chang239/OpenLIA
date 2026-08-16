import { useEffect, useRef } from "react";

// Renders a static design mockup (one of the /demo-mockups/*.html files) inside
// a Shadow DOM so its CSS is fully isolated from the app and vice versa. The
// mockup's own sidebar is stripped (the app supplies its shell) and its scripts
// are dropped (mostly-static demo); interaction wiring is done in onReady.

interface MockupEmbedProps {
  /** Public URL of the mockup HTML, e.g. "/demo-mockups/secretary.html". */
  url: string;
  className?: string;
  /** Extra selectors to remove from the mockup content before injection. */
  strip?: string[];
  /** Called once the content is in the shadow root; wire clicks/tabs here.
   *  Return a cleanup function to run on unmount / url change. */
  onReady?: (root: ShadowRoot) => void | (() => void);
}

// Resolve a root-absolute public path (e.g. "/demo-mockups/x.html") against the
// app's base URL so the mockups load when the demo is hosted under a sub-path
// (GitHub Pages project site). BASE_URL is "/" for normal builds — a no-op.
function publicUrl(path: string): string {
  if (!path.startsWith("/")) return path;
  return import.meta.env.BASE_URL.replace(/\/+$/, "") + path;
}

// Fetch a shared CSS file once and rehome its tokens/entrance selectors into the
// shadow scope (:root -> :host; the mockups' `html.om-anim body[data-om-auto]`
// entrance choreography -> `.om-anim-scope`, the class we add to each page root).
const cssCache = new Map<string, Promise<string>>();

function loadScopedCss(url: string): Promise<string> {
  let p = cssCache.get(url);
  if (!p) {
    p = fetch(publicUrl(url))
      .then((r) => (r.ok ? r.text() : ""))
      .then((css) =>
        css
          // Fonts come from the document; drop the mockup's own font loading.
          .replace(/@import[^;]+;/g, "")
          .replace(/@font-face\s*\{[^}]*\}/g, "")
          .replace(/html\.om-anim body\[data-om-auto\]/g, ".om-anim-scope")
          .replace(/html\.om-anim body/g, ".om-anim-scope")
          .replace(/:root/g, ":host"),
      )
      .catch(() => "");
    cssCache.set(url, p);
  }
  return p;
}

// The mockups lay out as `.app{display:grid;grid-template-columns:220px 1fr;
// height:100vh}` (sidebar + content). We drop the sidebar, so collapse the grid
// to a single full-width column and pin the app to the host's height so the
// internal scroll regions and split-view grids keep working.
const HOST_BASE = `:host{display:block;height:100%;overflow:hidden;background:var(--color-bg-base);color:var(--color-text-primary);font-family:var(--font-display)}
:host .app{grid-template-columns:1fr!important;height:100%!important;min-height:0!important}
:host aside.sidebar,:host .sidebar{display:none!important}`;

// Block navigation from the mockup's own local links; allow real external URLs.
function linkGuard(e: Event): void {
  const target = e.target as Element | null;
  const a = target?.closest?.("a[href]") as HTMLAnchorElement | null;
  if (!a) return;
  const href = a.getAttribute("href") ?? "";
  const isExternal = /^https?:\/\//i.test(href) && !href.includes(window.location.host);
  if (!isExternal) e.preventDefault();
}

export function MockupEmbed({ url, className, strip, onReady }: MockupEmbedProps): JSX.Element {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    let cancelled = false;
    let cleanup: void | (() => void);

    const root = host.shadowRoot ?? host.attachShadow({ mode: "open" });

    void (async () => {
      const [tokenCss, animCss, html] = await Promise.all([
        loadScopedCss("/demo-mockups/colors_and_type.css"),
        loadScopedCss("/demo-mockups/page-anim.css"),
        fetch(publicUrl(url)).then((r) => (r.ok ? r.text() : "")),
      ]);
      if (cancelled) return;

      const doc = new DOMParser().parseFromString(html, "text/html");
      doc.querySelectorAll("script").forEach((n) => n.remove());
      doc.querySelectorAll("aside.sidebar, .sidebar").forEach((n) => n.remove());
      for (const sel of strip ?? []) doc.querySelectorAll(sel).forEach((n) => n.remove());
      // Scripts are dropped, so inline event handlers (onclick="location.href=…",
      // handlers referencing now-undefined page functions) can only misfire —
      // strip them all; real interactions are wired via onReady.
      doc.querySelectorAll("*").forEach((el) => {
        for (const attr of Array.from(el.attributes)) {
          if (attr.name.startsWith("on")) el.removeAttribute(attr.name);
        }
      });

      // Tag the page root so the (scoped) entrance choreography plays on mount,
      // uniformly, even on the mockups whose <body> lacked data-om-auto.
      (doc.querySelector(".app") ?? doc.body.firstElementChild)?.classList.add(
        "om-anim-scope",
      );

      const pageCss = Array.from(doc.querySelectorAll("style"))
        .map((s) => s.textContent ?? "")
        .join("\n");
      doc.querySelectorAll("style").forEach((n) => n.remove());

      root.innerHTML =
        `<style>${tokenCss}\n${animCss}\n${HOST_BASE}\n${pageCss}</style>` +
        doc.body.innerHTML;

      // Sandbox the mockup: its own <a href="*.html"> links would otherwise
      // navigate the SPA to dead routes. Block local/relative/hash navigation so
      // clicks stay inside the demo; page-level onReady wiring adds real behavior.
      root.addEventListener("click", linkGuard);

      cleanup = onReady?.(root);
    })();

    return () => {
      cancelled = true;
      root.removeEventListener("click", linkGuard);
      if (typeof cleanup === "function") cleanup();
      if (host.shadowRoot) host.shadowRoot.innerHTML = "";
    };
  }, [url, strip, onReady]);

  return <div ref={hostRef} className={className} style={{ height: "100%" }} />;
}
