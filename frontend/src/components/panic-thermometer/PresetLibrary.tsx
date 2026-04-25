import { useState } from "react";
import type { PtPreset } from "../../api/panic-thermometer";

interface Props {
  presets: PtPreset[];
  onApply: (id: string) => void;
  onDelete: (id: string) => void;
  onSaveAs?: (name: string) => void;
  onRename?: (id: string, name: string) => void;
}

export function PresetLibrary({
  presets,
  onApply,
  onDelete,
  onSaveAs,
  onRename,
}: Props): JSX.Element {
  const [newName, setNewName] = useState<string>("");
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState<string>("");

  if (presets.length === 0 && !onSaveAs) {
    return <div>No presets available.</div>;
  }

  const shipped = presets.filter((p) => p.is_shipped);
  const custom = presets.filter((p) => !p.is_shipped);

  const submitRename = (id: string) => {
    if (onRename && renameValue.trim()) {
      onRename(id, renameValue.trim());
    }
    setRenamingId(null);
    setRenameValue("");
  };

  return (
    <div data-testid="preset-library" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
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
              {renamingId === p.id ? (
                <input
                  data-testid={`rename-input-${p.id}`}
                  type="text"
                  value={renameValue}
                  autoFocus
                  onChange={(e) => setRenameValue(e.target.value)}
                  onBlur={() => submitRename(p.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") submitRename(p.id);
                    if (e.key === "Escape") setRenamingId(null);
                  }}
                />
              ) : (
                <span>{p.name}</span>
              )}
              <span>
                <button type="button" onClick={() => onApply(p.id)}>
                  Apply
                </button>
                {onRename ? (
                  <button
                    type="button"
                    data-testid={`rename-btn-${p.id}`}
                    onClick={() => {
                      setRenamingId(p.id);
                      setRenameValue(p.name);
                    }}
                  >
                    Rename
                  </button>
                ) : null}
                <button type="button" onClick={() => onDelete(p.id)}>
                  Delete
                </button>
              </span>
            </li>
          ))}
        </ul>
        {onSaveAs ? (
          <div style={{ display: "flex", gap: "0.25rem", marginTop: "0.25rem" }}>
            <input
              type="text"
              data-testid="preset-save-name"
              placeholder="New preset name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <button
              type="button"
              data-testid="preset-save-btn"
              onClick={() => {
                if (newName.trim()) {
                  onSaveAs(newName.trim());
                  setNewName("");
                }
              }}
            >
              Save current as preset
            </button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
