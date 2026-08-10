// A tiny always-on badge that marks the build as a demo and states plainly that
// the data is illustrative. Rendered as a plain DOM node (no React) so demo
// wiring stays fully isolated from the app component tree.

export function mountDemoBadge(): void {
  if (document.getElementById("demo-badge")) return;

  const el = document.createElement("div");
  el.id = "demo-badge";
  el.setAttribute("role", "note");
  el.setAttribute(
    "aria-label",
    "Demo mode. Sample data, not real market data, and not investment advice.",
  );
  el.style.cssText = [
    "position:fixed",
    "left:12px",
    "bottom:12px",
    "z-index:2147483647",
    "display:flex",
    "align-items:center",
    "gap:8px",
    "padding:6px 11px",
    "border-radius:999px",
    "background:var(--color-sidebar-bg)",
    "color:var(--color-sidebar-text)",
    "font-family:'IBM Plex Mono',ui-monospace,monospace",
    "font-size:10px",
    "letter-spacing:0.08em",
    "text-transform:uppercase",
    "box-shadow:0 2px 12px rgba(0,0,0,0.25)",
    "pointer-events:none",
    "user-select:none",
  ].join(";");

  const dot = document.createElement("span");
  dot.style.cssText = [
    "width:7px",
    "height:7px",
    "border-radius:999px",
    "background:var(--color-accent-primary)",
    "box-shadow:0 0 6px rgba(var(--color-accent-primary-rgb),0.6)",
    "flex:0 0 auto",
  ].join(";");

  const label = document.createElement("span");
  label.textContent = "Demo — sample data, not advice";

  el.append(dot, label);
  document.body.appendChild(el);
}
