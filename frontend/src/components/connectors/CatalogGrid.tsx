import { CatalogCard } from "./CatalogCard";
import type { BuiltinTemplate } from "../../api/connectors";

interface Props {
  templates: BuiltinTemplate[];
  onSelect: (template: BuiltinTemplate) => void;
}

export function CatalogGrid({ templates, onSelect }: Props) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
      {templates.map((t) => (
        <CatalogCard
          key={t.template_id}
          template={t}
          onClick={() => onSelect(t)}
        />
      ))}
    </div>
  );
}
