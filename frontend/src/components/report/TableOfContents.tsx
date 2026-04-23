export interface TocSection {
  id: string;
  title: string;
}

export interface TableOfContentsProps {
  sections: TocSection[];
  activeId?: string;
}

export function TableOfContents({ sections, activeId }: TableOfContentsProps) {
  return (
    <nav className="report-toc" aria-label="Report sections">
      <ul>
        {sections.map((s) => {
          const isActive = s.id === activeId;
          return (
            <li key={s.id}>
              <a
                href={`#${s.id}`}
                aria-current={isActive ? 'true' : undefined}
                className={isActive ? 'report-toc__link--active' : undefined}
              >
                {s.title}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
