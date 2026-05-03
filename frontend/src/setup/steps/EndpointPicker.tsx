import { useState } from "react";

export interface EndpointOption {
  name: string;
  description?: string;
}

interface Props {
  options: EndpointOption[];
  value: string | null;
  onChange: (name: string) => void;
  disabled?: boolean;
}

export function EndpointPicker({ options, value, onChange, disabled }: Props) {
  const [query, setQuery] = useState("");
  const filtered = options.filter((opt) =>
    opt.name.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <div className="endpoint-picker">
      <input
        type="text"
        placeholder="Search endpoints…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        disabled={disabled}
        aria-label="Search endpoints"
      />
      <ul role="listbox">
        {filtered.map((opt) => (
          <li
            key={opt.name}
            role="option"
            aria-selected={value === opt.name}
          >
            <button
              type="button"
              onClick={() => onChange(opt.name)}
              disabled={disabled}
              data-selected={value === opt.name}
            >
              <span>{opt.name}</span>
              {opt.description ? (
                <small>{opt.description}</small>
              ) : null}
            </button>
          </li>
        ))}
        {filtered.length === 0 ? <li>(no matches)</li> : null}
      </ul>
    </div>
  );
}
