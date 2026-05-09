export interface TocSection {
  id: string;
  title: string;
}

export interface TableOfContentsProps {
  sections: TocSection[];
  activeId?: string;
  onSectionClick?: (id: string) => void;
}

export function TableOfContents({ sections, activeId, onSectionClick }: TableOfContentsProps) {
  return (
    <nav className="report-toc" aria-label="Report sections">
      <ul>
        {sections.map((s, i) => {
          const isActive = s.id === activeId;
          return (
            <li key={s.id}>
              <a
                href={`#${s.id}`}
                aria-current={isActive ? 'true' : undefined}
                className={isActive ? 'report-toc__link--active' : undefined}
                onClick={() => onSectionClick?.(s.id)}
              >
                <span className="report-toc__num">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <span className="report-toc__title">{s.title}</span>
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
