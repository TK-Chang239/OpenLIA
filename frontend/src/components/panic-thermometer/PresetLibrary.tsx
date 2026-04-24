import type { PtPreset } from "../../api/panic-thermometer";

interface Props {
  presets: PtPreset[];
  onApply: (id: string) => void;
  onDelete: (id: string) => void;
}

export function PresetLibrary({ presets, onApply, onDelete }: Props): JSX.Element {
  if (presets.length === 0) {
    return <div>No presets available.</div>;
  }
  const shipped = presets.filter((p) => p.is_shipped);
  const custom = presets.filter((p) => !p.is_shipped);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <section>
        <h4>Shipped library ({shipped.length})</h4>
        <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
          {shipped.map((p) => (
            <li
              key={p.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "0.25rem 0",
              }}
            >
              <span>{p.name}</span>
              <button type="button" onClick={() => onApply(p.id)}>
                Apply
              </button>
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h4>Your presets ({custom.length})</h4>
        <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
          {custom.map((p) => (
            <li
              key={p.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "0.25rem 0",
              }}
            >
              <span>{p.name}</span>
              <span>
                <button type="button" onClick={() => onApply(p.id)}>
                  Apply
                </button>
                <button type="button" onClick={() => onDelete(p.id)}>
                  Delete
                </button>
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
