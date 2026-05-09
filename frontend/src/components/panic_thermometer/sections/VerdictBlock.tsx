import type { JSX } from "react";
import type { VerdictCopy } from "../../../lib/panic_thermometer/copy/types";

interface Props {
  verdict: VerdictCopy;
  variant?: "severe" | "default";
}

export function VerdictBlock({ verdict, variant = "severe" }: Props): JSX.Element {
  return (
    <>
      <div className="pt-sec-label">
        <span>LIA · verdict</span>
        <span className="pt-ln" />
        <span className="pt-count">
          {verdict.generatedAt} · confidence {verdict.confidence}
        </span>
      </div>

      <article
        className={`pt-verdict ${variant === "severe" ? "is-severe" : ""}`}
        aria-label="LIA verdict"
      >
        <div className="pt-badge">LIA</div>
        <div className="pt-body">
          <div className="pt-meta">
            {verdict.metaParts.map((p, i) => (
              <span
                key={i}
                style={{ display: "inline-flex", alignItems: "center", gap: 10 }}
              >
                <span>{p}</span>
                {i < verdict.metaParts.length - 1 ? <span className="pt-dot" /> : null}
              </span>
            ))}
          </div>
          <h2>{verdict.headline}</h2>
          {verdict.paragraphs.map((para, idx) => (
            <p key={idx}>
              {para.parts.map((part, j) =>
                part.kind === "text" ? (
                  <span key={j}>{part.value}</span>
                ) : (
                  <strong key={j} className={part.tone ? `is-${part.tone}` : undefined}>
                    {part.value}
                  </strong>
                ),
              )}
            </p>
          ))}
          <div className="pt-tags">
            {verdict.tags.map((t, i) => (
              <a key={i} className="pt-tag" href={t.href}>
                {t.label}
              </a>
            ))}
          </div>
        </div>
      </article>
    </>
  );
}
